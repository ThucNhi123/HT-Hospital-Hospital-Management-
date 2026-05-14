import datetime
from datetime import date, timedelta, time, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.db import connection
from django.utils import timezone
from sqlalchemy import text
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Sum

from api.forms import SignUpForm
from .manager_functions import get_patient_medical_history, get_all_doctors, book_appointment
from .connect_database import engine
from .models import Appointment, Patient

# =====================================================================
# 1. AUTHENTICATION VIEWS (ĐĂNG NHẬP / ĐĂNG KÝ / ĐĂNG XUẤT)
# =====================================================================

def sign_in_view(request):
    """
    Xử lý đăng nhập cho người dùng. 
    Kiểm tra hợp lệ và điều hướng theo phân quyền nhóm (Group: Doctor, Receptionist, Patient).
    """
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Điều hướng theo phân quyền
                if user.groups.filter(name='Doctor').exists():
                    return redirect('doctor_dashboard')
                elif user.groups.filter(name='Receptionist').exists():
                    return redirect('reception_dashboard')
                else:
                    return redirect('patient_dashboard') # Mặc định
            else:
                messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
        else:
            messages.error(request, 'Thông tin không hợp lệ.')
    else:
        form = AuthenticationForm()
    return render(request, 'api/sign_in.html', {'form': form})

def sign_up_view(request):
    """
    Xử lý đăng ký tài khoản mới. 
    Cập nhật username theo ID và tự động gán vào nhóm 'Patient'.
    """
    success = False  
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Cập nhật username thành "ID - Username" sau khi đã có user.id
            user.username = f"{user.id} - {user.username}"
            user.save()
            
            # Tự động gán quyền Patient
            group, created = Group.objects.get_or_create(name='Patient')
            user.groups.add(group)
            
            success = True 
    else:
        form = SignUpForm()
        
    return render(request, 'api/sign_up.html', {'form': form, 'success': success})

def sign_out_view(request):
    """
    Xử lý đăng xuất tài khoản và chuyển hướng về trang đăng nhập.
    """
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất.')
    return redirect('sign_in')

# =====================================================================
# 2. PATIENT DASHBOARD & HÀM XỬ LÝ DỮ LIỆU BỆNH NHÂN
# =====================================================================

def is_patient(user):
    """Kiểm tra xem user có thuộc nhóm Patient không."""
    return user.groups.filter(name='Patient').exists()

@login_required(login_url='sign_in')
@user_passes_test(is_patient, login_url='sign_in')
def patient_dashboard_view(request):
    """
    Xử lý dữ liệu hiển thị cho bệnh nhân: thông tin cá nhân, lịch hẹn, lịch sử khám, và hóa đơn (Billing).
    """
    patient_id = None
    patient = {}
    
    try:
        # Giữ nguyên logic lấy ID từ username
        patient_id = request.user.username.split('-')[0].strip()
    except Exception:
        patient_id = None

    # Xử lý các thao tác qua form POST
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Thêm lịch hẹn mới
        if action == 'add_appointment':
            doctor_id = request.POST.get('doctor_id')
            appt_date = request.POST.get('appt_date')
            appt_time = request.POST.get('appt_time')
            reason = request.POST.get('reason')
            # symptom = request.POST.get('symptom') # Nếu cần dùng trong book_appointment
            
            try:
                # Hàm book_appointment bên trong cũng cần đảm bảo dùng đúng tên cột mới
                book_appointment(patient_id, doctor_id, appt_date, appt_time, reason)
                messages.success(request, "Đặt lịch khám thành công!")
            except Exception as e:
                messages.error(request, f"Lỗi đặt lịch: {e}")
                
        # Thêm hóa đơn mới (Cập nhật sang bảng Billing)
        elif action == 'add_invoice':
            amount = request.POST.get('Amount')
            bill_date = request.POST.get('InvoiceDate') # Form gửi InvoiceDate nhưng nạp vào bill_date
            
            try:
                with engine.connect() as conn:
                    # Đổi sang bảng Billing, các cột bill_id (nếu không auto-increment), patient_id, amount, bill_date
                    query = text("""
                        INSERT INTO Billing (patient_id, amount, bill_date, payment_status)
                        VALUES (:pid, :amount, :date, 'Pending')
                    """)
                    conn.execute(query, {
                        "pid": patient_id,
                        "amount": amount,
                        "date": bill_date
                    })
                    conn.commit()
                    messages.success(request, "Thêm hóa đơn thành công!")
            except Exception as e:
                messages.error(request, f"Lỗi thêm hóa đơn: {e}")

    # 1. Lấy thông tin cá nhân (Cập nhật patient_id)
    patient = {}
    if patient_id:
        try:
            with engine.connect() as conn:
                query = text("SELECT * FROM Patients WHERE patient_id = :pid")
                result = conn.execute(query, {"pid": patient_id}).mappings().first()
                if result:
                    patient = dict(result)
        except Exception:
            pass

    # 2. Lấy lịch sử và lịch hẹn (Dùng dữ liệu từ get_patient_medical_history)
    medical_history = []
    appointments = []
    
    if patient_id:
        all_history = get_patient_medical_history(patient_id)
        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()

        with engine.connect() as conn: 
            for item in all_history:
                aid = item.get('appointment_id')
                appt_date = item.get('appointment_date')
                appt_time = item.get('appointment_time')
                current_status = item.get('status')
                display_status = current_status
                
                if isinstance(appt_time, timedelta):
                    total_seconds = int(appt_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    appt_time_obj = time(hours, minutes)
                # Nếu là chuỗi "HH:MM:SS"
                elif isinstance(appt_time, str):
                    try:
                        appt_time_obj = datetime.strptime(appt_time, "%H:%M:%S").time()
                    except:
                        appt_time_obj = datetime.strptime(appt_time, "%H:%M").time()
                else:
                    appt_time_obj = appt_time

                # --- BƯỚC 2: KIỂM TRA QUÁ GIỜ (NO-SHOW) ---
                is_past = (appt_date < today) or (appt_date == today and appt_time_obj < current_time)

                if is_past and item.get('status') == 'Scheduled':
                    # THỰC HIỆN CẬP NHẬT TRỰC TIẾP TRONG DATABASE
                    update_query = text("""
                        UPDATE Appointments 
                        SET status = 'No-show' 
                        WHERE appointment_id = :aid
                    """)
                    conn.execute(update_query, {"aid": aid})
                    conn.commit() # Lưu thay đổi
                    
                    # Cập nhật lại giá trị trong item để hiển thị luôn mà không cần reload lần 2
                    item['status'] = 'No-show'
                
                item['display_status'] = display_status
                item['formatted_time'] = appt_time_obj.strftime("%H:%M") if appt_time_obj else "--:--"

                # --- BƯỚC 3: PHÂN BẢNG ---
                # Luôn hiện ở Medical History
                medical_history.append(item)
                
                # Chỉ hiện ở My Appointments nếu chưa quá giờ và chưa bị hủy/khám xong
                if not is_past and current_status == 'Scheduled':
                    appointments.append(item)

    # 3. Lấy thông tin hóa đơn (Billing)
    invoices = []
    total_amount_formatted = "0"
    
    if patient_id:
        try:
            with engine.connect() as conn:
                # Lấy thêm payment_method và payment_status
                query = text("""
                    SELECT bill_id, bill_date, amount, payment_method, payment_status 
                    FROM Billing 
                    WHERE patient_id = :pid 
                    ORDER BY bill_date DESC
                """)
                result = conn.execute(query, {"pid": patient_id}).mappings().all()
                
                temp_invoices = []
                for row in result:
                    inv = dict(row)
                    inv['formatted_amount'] = format_number(inv.get('amount'))
                    temp_invoices.append(inv)
                invoices = temp_invoices
                
                sum_query = text("SELECT SUM(amount) FROM Billing WHERE patient_id = :pid")
                total_amount_raw = conn.execute(sum_query, {"pid": patient_id}).scalar() or 0
                total_amount_formatted = format_number(total_amount_raw)
        except Exception as e:
            print(f"Lỗi tải hóa đơn: {e}")
                
    doctors_list = get_all_doctors()
        
    context = {
        'user': request.user,
        'patient_id': patient_id,
        'patient': patient,
        'medical_history': medical_history, 
        'appointments': appointments,        
        'doctors_list': doctors_list,
        'invoices': invoices, # Giữ key name cho template không bị lỗi
        'total_amount': total_amount_formatted,
    }
    return render(request, 'api/patient_dashboard.html', context)

def format_number(value):
    """Hàm định dạng số (Dấu phẩy ngăn cách hàng nghìn, dấu chấm thập phân)."""
    if value is None:
        return "0"
    try:
        formatted = f"{float(value):,.2f}" 
        if formatted.endswith(".00"):
            formatted = formatted[:-3]
        return formatted
    except Exception:
        return str(value)

def delete_appointment(request, appointment_id):
    if request.method == 'POST':
        # Cập nhật trạng thái thành 'Cancelled'
        query = text("UPDATE Appointments SET status = 'Cancelled' WHERE appointment_id = :aid")
        try:
            with engine.connect() as conn:
                conn.execute(query, {"aid": appointment_id})
                conn.commit()
                return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
            
    return redirect('patient_dashboard')

def update_profile(request):
    """Cập nhật hoặc thêm mới thông tin cá nhân trong cơ sở dữ liệu."""
    if request.method == 'POST':
        # Lấy dữ liệu từ form (giữ nguyên key của POST để bạn không phải sửa HTML)
        patient_id = request.POST.get('PatientID')
        full_name = request.POST.get('FullName')
        dob = request.POST.get('DOB')
        phone = request.POST.get('PhoneNumber')
        address = request.POST.get('Address')
        gender = request.POST.get('Gender')

        try:
            with engine.connect() as conn:
                # 1. Kiểm tra xem bệnh nhân đã có trong bảng Patients chưa
                check_query = text("SELECT COUNT(*) FROM Patients WHERE patient_id = :pid")
                count = conn.execute(check_query, {"pid": patient_id}).scalar()

                if count > 0:
                    # UPDATE: Cập nhật theo tên cột mới
                    update_query = text("""
                        UPDATE Patients 
                        SET first_name = :name, last_name = '', date_of_birth = :dob, 
                            contact_number = :phone, address = :address, gender = :gender
                        WHERE patient_id = :pid
                    """)
                    conn.execute(update_query, {
                        "name": full_name, 
                        "dob": dob if dob else None, 
                        "phone": phone, 
                        "address": address, 
                        "gender": gender, 
                        "pid": patient_id
                    })
                else:
                    # INSERT: Thêm mới theo tên cột mới
                    insert_query = text("""
                        INSERT INTO Patients (patient_id, first_name, last_name, date_of_birth, contact_number, address, gender)
                        VALUES (:pid, :name, '', :dob, :phone, :address, :gender)
                    """)
                    conn.execute(insert_query, {
                        "pid": patient_id, 
                        "name": full_name, 
                        "dob": dob if dob else None, 
                        "phone": phone, 
                        "address": address, 
                        "gender": gender
                    })
                
                conn.commit()
                messages.success(request, "Cập nhật thông tin cá nhân thành công!")
        except Exception as e:
            messages.error(request, f"Lỗi cập nhật: {e}")

    return redirect('patient_dashboard')

def check_availability(request):
    doctor_id = request.GET.get('doctor_id')
    date = request.GET.get('date')
    
    query = text("""
        SELECT appointment_time 
        FROM Appointments 
        WHERE doctor_id = :did AND appointment_date = :adate AND status != 'Cancelled'
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"did": doctor_id, "adate": date}).fetchall()
        # Định dạng lại giờ để khớp với JS (ví dụ: "08:00:00" -> "08:00")
        booked_slots = [row[0].strftime("%H:%M") if hasattr(row[0], 'strftime') else str(row[0])[:5] for row in result]
        
    return JsonResponse({'booked_slots': booked_slots})


# =====================================================================
# 3. DOCTOR DASHBOARD
# =====================================================================
def is_doctor(user):
    return user.groups.filter(name__in=['Doctor']).exists()

@login_required(login_url='sign_in')
@user_passes_test(is_doctor, login_url='sign_in')
def doctor_dashboard_view(request):
    doctor_id = None
    doctor = {}
    appointments = []

    # Lấy tham số từ URL
    selected_date_str = request.GET.get('date')
    view_mode = request.GET.get('view_mode', 'day') # Mặc định là 'day'

    # Xử lý ngày tháng
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    # Tách mã bác sĩ từ username (Giữ nguyên logic của bạn)
    try:
        username = request.user.username
        if '-' in username:
            doctor_id = username.split('-')[0].strip()
        elif '_' in username:
            doctor_id = username.split('_')[0].strip()
        else:
            doctor_id = username
    except Exception:
        doctor_id = None

    if doctor_id:
        try:
            with engine.connect() as conn:
                # 1. Lấy thông tin bác sĩ (Theo bảng Doctors và cột doctor_id)
                query_doc = text("SELECT * FROM Doctors WHERE doctor_id = :did")
                result_doc = conn.execute(query_doc, {"did": doctor_id}).mappings().first()
                if result_doc:
                    doctor = dict(result_doc)

                # 2. Xử lý truy vấn theo chế độ (Ngày / Tuần)
                # Cập nhật JOIN theo cột patient_id và lấy tên bệnh nhân bằng cách nối chuỗi
                if view_mode == 'week':
                    end_date = selected_date + timedelta(days=6)
                    query_app = text("""
                        SELECT a.appointment_id, a.appointment_date, a.appointment_time,  a.reason_for_visit, a.status,
                               p.patient_id, p.first_name, p.last_name
                        FROM Appointments a
                        JOIN Patients p ON a.patient_id = p.patient_id
                        WHERE a.doctor_id = :did 
                          AND a.appointment_date >= :start_date 
                          AND a.appointment_date <= :end_date
                        ORDER BY a.appointment_date ASC, a.appointment_time ASC
                    """)
                    result_app = conn.execute(query_app, {
                        "did": doctor_id, 
                        "start_date": selected_date, 
                        "end_date": end_date
                    }).mappings().all()
                else:
                    query_app = text("""
                        SELECT a.appointment_id, a.appointment_date, a.appointment_time, a.reason_for_visit, a.status,
                               p.patient_id, p.first_name, p.last_name
                        FROM Appointments a
                        JOIN Patients p ON a.patient_id = p.patient_id
                        WHERE a.doctor_id = :did 
                          AND a.appointment_date = :date
                        ORDER BY a.appointment_time ASC
                    """)
                    result_app = conn.execute(query_app, {
                        "did": doctor_id, 
                        "date": selected_date
                    }).mappings().all()
                
                # Chuyển kết quả thành list dict và xử lý hiển thị tên
                appointments = []
                for row in result_app:
                    d = dict(row)
                    # Tạo thêm key 'patient_fullname' để dễ hiển thị ở template
                    d['patient_fullname'] = f"{d['first_name']} {d['last_name']}"
                    appointments.append(d)
                
        except Exception as e:
            print(f"Error loading dashboard data: {e}")

    context = {
        'user': request.user,
        'doctor_id': doctor_id,
        'doctor': doctor,
        'appointments': appointments,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'view_mode': view_mode,
    }
    
    return render(request, 'api/doctor_dashboard.html', context)

@csrf_exempt
def create_treatment_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            appointment_id = data.get('appointment_id')
            patient_id = data.get('patient_id')
            treatment_type = data.get('treatment_type')
            description = data.get('description')
            cost = float(data.get('cost'))
            
            with engine.begin() as conn: # Sử dụng 'begin' để tự động COMMIT hoặc ROLLBACK nếu lỗi
                # 1. Lấy ID mới cho Treatment (Txxx)
                res_t = conn.execute(text("SELECT treatment_id FROM Treatments ORDER BY treatment_id DESC LIMIT 1")).fetchone()
                if res_t:
                    new_t_id = f"T{int(res_t[0][1:]) + 1:03d}"
                else:
                    new_t_id = "T001"

                # 2. Lưu vào bảng Treatments
                conn.execute(text("""
                    INSERT INTO Treatments (treatment_id, appointment_id, treatment_type, description, cost, treatment_date)
                    VALUES (:tid, :aid, :ttype, :desc, :cost, :tdate)
                """), {
                    "tid": new_t_id, "aid": appointment_id, "ttype": treatment_type,
                    "desc": description, "cost": cost, "tdate": date.today()
                })

                # 3. Lấy ID mới cho Billing (Bxxx)
                res_b = conn.execute(text("SELECT bill_id FROM Billing ORDER BY bill_id DESC LIMIT 1")).fetchone()
                if res_b:
                    new_b_id = f"B{int(res_b[0][1:]) + 1:03d}"
                else:
                    new_b_id = "B001"

                # 4. Lưu vào bảng Billing (Trạng thái Pending)
                conn.execute(text("""
                    INSERT INTO Billing (bill_id, patient_id, treatment_id, bill_date, amount, payment_method, payment_status)
                    VALUES (:bid, :pid, :tid, :bdate, :amt, 'Unspecified', 'Pending')
                """), {
                    "bid": new_b_id, "pid": patient_id, "tid": new_t_id,
                    "bdate": date.today(), "amt": cost
                })

            return JsonResponse({'status': 'success', 'message': 'Hồ sơ bệnh án và hóa đơn đã được tạo thành công!'})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def get_treatment_history(request, appointment_id): # Tên tham số phải là appointment_id
    try:
        with engine.connect() as conn:
            # Lọc trực tiếp theo appointment_id để lấy đúng các dịch vụ của lần khám đó
            query = text("""
                SELECT t.treatment_date, t.treatment_type, t.description, t.cost 
                FROM Treatments t
                WHERE t.appointment_id = :aid
                ORDER BY t.treatment_id DESC
            """)
            result = conn.execute(query, {"aid": appointment_id}).mappings().all()
            history = [dict(row) for row in result]
            
            return JsonResponse({'status': 'success', 'history': history})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def my_patients_view(request):
    doctor_id = None
    patients = []

    try:
        username = request.user.username
        if '-' in username:
            doctor_id = username.split('-')[0].strip()
        elif '_' in username:
            doctor_id = username.split('_')[0].strip()
        else:
            doctor_id = username
    except Exception:
        doctor_id = None

    if doctor_id:
        try:
            with engine.connect() as conn:
                # SỬA TẠI ĐÂY: Thay đổi toàn bộ PatientID, PatientName... thành tên cột mới
                query = text("""
                    SELECT DISTINCT 
                        p.patient_id, 
                        p.first_name, 
                        p.last_name, 
                        p.date_of_birth, 
                        p.gender, 
                        p.address, 
                        p.contact_number
                    FROM Patients p
                    JOIN Appointments a ON p.patient_id = a.patient_id
                    WHERE a.doctor_id = :did
                """)
                
                result = conn.execute(query, {"did": doctor_id}).mappings().all()
                
                # Chuyển kết quả và ghép tên để hiển thị ở template
                patients = []
                for row in result:
                    p_dict = dict(row)
                    p_dict['full_name'] = f"{p_dict['first_name']} {p_dict['last_name']}"

                    gender_code = str(p_dict.get('gender', '')).upper()
                    if gender_code == 'M':
                        p_dict['gender_display'] = 'Male'
                    elif gender_code == 'F':
                        p_dict['gender_display'] = 'Female'
                    else:
                        p_dict['gender_display'] = p_dict.get('gender')

                    patients.append(p_dict)
                
        except Exception as e:
            print(f"Error loading patients: {e}")

    context = {
        'user': request.user,
        'patients': patients,
    }
    
    return render(request, 'api/my_patients.html', context)

def patient_detail_view(request, patient_id):
    patient = {}
    past_appointments = []
    upcoming_appointments = []

    try:
        username = request.user.username
        if '-' in username:
            doctor_id = username.split('-')[0].strip()
        elif '_' in username:
            doctor_id = username.split('_')[0].strip()
        else:
            doctor_id = username

        print(f"DEBUG >>> patient_id={patient_id}, doctor_id={doctor_id}")  # <-- thêm dòng này

        with engine.connect() as conn:
            p_query = text("SELECT * FROM Patients WHERE patient_id = :pid")
            p_result = conn.execute(p_query, {"pid": patient_id}).mappings().first()
            print(f"DEBUG >>> patient result: {p_result}")  # <-- thêm dòng này
            if p_result:
                patient = dict(p_result)
                patient['full_name'] = f"{patient['first_name']} {patient['last_name']}"

            app_query = text("""
                SELECT 
                    a.appointment_id, 
                    a.appointment_date, 
                    a.appointment_time, 
                    a.status,
                    a.reason_for_visit,
                    t.treatment_type, 
                    t.description
                FROM Appointments a
                LEFT JOIN Treatments t ON a.appointment_id = t.appointment_id
                WHERE a.patient_id = :pid AND a.doctor_id = :did
                ORDER BY a.appointment_date DESC, a.appointment_time DESC
            """)
            apps = conn.execute(app_query, {"pid": patient_id, "did": doctor_id}).mappings().all()
            print(f"DEBUG >>> appointments count: {len(apps)}")  # <-- thêm dòng này

            today = date.today()

            for app in apps:
                app_dict = dict(app)
                app_date = app_dict.get('appointment_date')

                if isinstance(app_date, datetime):
                    app_date = app_date.date()
                elif isinstance(app_date, str):
                    app_date = datetime.strptime(app_date, "%Y-%m-%d").date()

                if app_date and app_date < today:
                    past_appointments.append(app_dict)
                else:
                    upcoming_appointments.append(app_dict)

    except Exception as e:
        print(f"ERROR >>> {e}")  # <-- quan trọng nhất, xem lỗi gì

    context = {
        'user': request.user,
        'patient': patient,
        'past_appointments': past_appointments,
        'upcoming_appointments': upcoming_appointments,
    }
    
    return render(request, 'api/patient_detail.html', context)

# =====================================================================
# 4. RECEPTIONISTS
# =====================================================================
def is_reception_or_billing(user):
    return user.groups.filter(name__in=['Receptionist']).exists()
 
@login_required(login_url='sign_in')
@user_passes_test(is_reception_or_billing, login_url='sign_in')
def reception_billing_dashboard_view(request):
    patients_queue = []
    doctors = []
    specialties = []
    
    # 1. Lấy tham số từ URL (Sử dụng cho cả Queue và Form đăng ký)
    # ?date=YYYY-MM-DD & ?doctor_id=Dxxx
    selected_date_str = request.GET.get('date', date.today().strftime('%Y-%m-%d'))
    selected_doctor = request.GET.get('doctor_id', '')
    
    booked_slots = []
 
    try:
        with engine.connect() as conn:
            # Lấy danh sách chuyên khoa
            spec_query = text("SELECT DISTINCT specialization FROM doctors WHERE specialization IS NOT NULL")
            specialties = [row[0] for row in conn.execute(spec_query).all()]
            
            # Lấy danh sách bác sĩ (Lấy cả first_name và last_name)
            doc_query = text("SELECT doctor_id, first_name, last_name, specialization FROM doctors")
            doctors = [dict(row) for row in conn.execute(doc_query).mappings().all()]
            
            # 2. Lấy các giờ đã đặt của NGÀY ĐANG CHỌN (Để hiện màu đỏ/xanh)
            query_booked = text("""
                SELECT appointment_time FROM appointments 
                WHERE appointment_date = :selected_date 
                AND doctor_id = :doc_id
                AND status != 'Cancelled'
            """)
            
            # Chỉ thực hiện query nếu đã chọn bác sĩ
            if selected_doctor:
                booked_results = conn.execute(query_booked, {
                    "selected_date": selected_date_str, 
                    "doc_id": selected_doctor
                }).all()
                
                # Chuyển thành list ["08:00", "09:00", ...]
                booked_slots = [
                    row[0].strftime('%H:%M') if hasattr(row[0], 'strftime') else str(row[0])[:5] 
                    for row in booked_results
                ]
            else:
                booked_slots = []
 
            # 3. Truy vấn hàng đợi theo NGÀY ĐANG CHỌN (Today's Queue)
            # Dùng CONCAT để hiển thị Dr. Full Name
            query_queue = text("""
                SELECT 
                    p.patient_id, p.first_name, p.last_name, 
                    a.appointment_id, a.appointment_time, a.appointment_date, a.reason_for_visit,
                    CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                    t.treatment_id, t.treatment_type, t.description as treatment_desc, t.cost,
                    b.bill_id, b.payment_status
                FROM appointments a
                JOIN patients p ON a.patient_id = p.patient_id
                JOIN doctors d ON a.doctor_id = d.doctor_id
                LEFT JOIN treatments t ON a.appointment_id = t.appointment_id
                LEFT JOIN billing b ON t.treatment_id = b.treatment_id
                WHERE CAST(a.appointment_date AS DATE) = :selected_date
                ORDER BY a.appointment_time ASC
            """)
            raw_results = conn.execute(query_queue, {"selected_date": selected_date_str}).mappings().all()
 
            # Nhóm dữ liệu bằng Python để tránh lặp dòng trên giao diện
            queue_dict = {}
            for row in raw_results:
                appt_id = row['appointment_id']
                if appt_id not in queue_dict:
                    # Nếu chưa có lịch hẹn này trong dict, tạo mới
                    queue_dict[appt_id] = {
                        'patient_id': row['patient_id'],
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'appointment_time': row['appointment_time'],
                        'appointment_date': row['appointment_date'],
                        'reason_for_visit': row['reason_for_visit'],
                        'doctor_name': row['doctor_name'],
                        'treatments': [],  # Danh sách các dịch vụ
                        'total_cost': 0,
                        'bill_id': None,
                        'payment_status': 'Pending'
                    }
                
                # Nếu có treatment, đẩy vào danh sách của bệnh nhân đó
                if row['treatment_id']:
                    queue_dict[appt_id]['treatments'].append({
                        'type': row['treatment_type'],
                        'desc': row['treatment_desc'],
                        'cost': float(row['cost'] or 0)
                    })
                    queue_dict[appt_id]['total_cost'] += float(row['cost'] or 0)
                    queue_dict[appt_id]['bill_id'] = row['bill_id']
                    queue_dict[appt_id]['payment_status'] = row['payment_status']
 
            # Chuyển Dictionary thành List để gửi xuống Template
            patients_queue = list(queue_dict.values())
            
            # Chuyển danh sách treatments của mỗi bệnh nhân thành chuỗi JSON để JS dễ đọc
            import json
            for p in patients_queue:
                p['treatments_json'] = json.dumps(p['treatments'])
 
    except Exception as e:
        print(f"Error: {e}")
 
    # XỬ LÝ ĐĂNG KÝ (POST)
    if request.method == 'POST':
        # Thu thập dữ liệu Patient (Dựa trên Ảnh màn hình 10.52.43.png)
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number')
        gender = request.POST.get('gender')
        dob = request.POST.get('dob')
        address = request.POST.get('address')
        email = request.POST.get('email')
        ins_provider = request.POST.get('insurance_provider')
        ins_number = request.POST.get('insurance_number')
        
        # Thu thập dữ liệu Appointment
        doctor_id = request.POST.get('doctor_id')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        reason_for_visit = request.POST.get('reason_for_visit')
 
        try:
            with engine.connect() as conn:
                # BƯỚC 1: KIỂM TRA/TẠO BỆNH NHÂN (Bảng Patients)
                check_patient = text("SELECT patient_id FROM patients WHERE contact_number = :phone OR email = :email")
                existing_patient = conn.execute(check_patient, {"phone": phone_number, "email": email}).mappings().first()
                
                if existing_patient:
                    patient_id = existing_patient['patient_id']
                else:
                    max_p_query = text("SELECT patient_id FROM patients ORDER BY patient_id DESC LIMIT 1")
                    max_p_result = conn.execute(max_p_query).scalar()
                    patient_id = f"P{int(max_p_result[1:]) + 1:03d}" if max_p_result else "P001"
                    
                    conn.execute(text("""
                        INSERT INTO patients (
                            patient_id, first_name, last_name, date_of_birth, gender, 
                            contact_number, address, insurance_provider, insurance_number, email, registration_date
                        )
                        VALUES (
                            :pid, :fname, :lname, :dob, :gender, 
                            :phone, :addr, :ins_p, :ins_n, :email, :reg_date
                        )
                    """), {
                        "pid": patient_id, "fname": first_name, "lname": last_name, 
                        "dob": dob, "gender": gender, "phone": phone_number, 
                        "addr": address, "ins_p": ins_provider, 
                        "ins_n": ins_number, "email": email, "reg_date": date.today()
                    })
                    
                # BƯỚC 2: TẠO LỊCH HẸN (Bảng Appointments)
                max_a_query = text("SELECT appointment_id FROM appointments ORDER BY appointment_id DESC LIMIT 1")
                max_a_result = conn.execute(max_a_query).scalar()
                appointment_id = f"A{int(max_a_result[1:]) + 1:03d}" if max_a_result else "A001"
                
                conn.execute(text("""
                    INSERT INTO appointments (appointment_id, patient_id, doctor_id, appointment_date, appointment_time, reason_for_visit, status)
                    VALUES (:aid, :pid, :did, :adate, :atime, :reason, 'Scheduled')
                """), {
                    "aid": appointment_id, "pid": patient_id, "did": doctor_id, 
                    "adate": appointment_date, "atime": appointment_time, "reason": reason_for_visit
                })
                
                conn.commit()
                messages.success(request, f"Successfully registered {first_name} {last_name}!")
                # Redirect về đúng ngày đang chọn để xem hàng đợi ngay lập tức
                return redirect(f'/reception-dashboard/?date={appointment_date}')
 
        except Exception as e:
            conn.rollback()
            print(f"Error details: {e}")
            messages.error(request, f"Database Error: {e}")
 
    # Cấu hình Slot giờ khám cố định
    time_slots = [
        {'label': '08:00 - 09:00', 'value': '08:00'},
        {'label': '09:00 - 10:00', 'value': '09:00'},
        {'label': '10:00 - 11:00', 'value': '10:00'},
        {'label': '13:00 - 14:00', 'value': '13:00'},
        {'label': '14:00 - 15:00', 'value': '14:00'},
        {'label': '15:00 - 16:00', 'value': '15:00'},
    ]
 
    context = {
        'patients_queue': patients_queue,
        'specialties': specialties,
        'doctors': doctors,
        'time_slots': time_slots,
        'booked_slots': booked_slots,
        'selected_date': selected_date_str,
        'selected_doctor': selected_doctor,
        'today_str': date.today().strftime('%Y-%m-%d'),
        'current_time': datetime.now().strftime('%H:%M'),
    }
    return render(request, 'api/receptionist_dashboard.html', context)
 
def confirm_payment_view(request, bill_id):
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        try:
            with engine.connect() as conn:
                # 1. Tìm appointment_id từ bill_id đang thanh toán
                find_appt = text("""
                    SELECT t.appointment_id 
                    FROM treatments t 
                    JOIN billing b ON t.treatment_id = b.treatment_id 
                    WHERE b.bill_id = :bid
                """)
                appt_id = conn.execute(find_appt, {"bid": bill_id}).scalar()
 
                if appt_id:
                    # 2. Cập nhật trạng thái thanh toán là 'Paid' cho tất cả bill của ca khám này
                    conn.execute(text("""
                        UPDATE billing 
                        SET payment_status = 'Paid', payment_method = :method 
                        WHERE treatment_id IN (
                            SELECT treatment_id FROM treatments WHERE appointment_id = :aid
                        )
                    """), {"method": payment_method, "aid": appt_id})

                    # 3. Cập nhật trạng thái cuộc hẹn thành 'Completed'
                    conn.execute(text("""
                        UPDATE appointments 
                        SET status = 'Completed' 
                        WHERE appointment_id = :aid
                    """), {"aid": appt_id})
                    
                    conn.commit()
                    messages.success(request, f"Đã thanh toán và hoàn tất ca khám {appt_id}!")
        except Exception as e:
            messages.error(request, f"Lỗi khi xác nhận thanh toán: {e}")
            
    return redirect('reception_dashboard')
 
@login_required
@user_passes_test(lambda u: u.groups.filter(name='Receptionist').exists())
def get_all_patient_records(request):
    search_query = request.GET.get('search', '')
    
    with engine.connect() as conn:
        sql = """
            SELECT patient_id, first_name, last_name, gender, 
                   contact_number, date_of_birth, address 
            FROM patients WHERE 1=1
        """
        params = {}
        if search_query:
            sql += " AND (first_name LIKE :q OR last_name LIKE :q OR patient_id LIKE :q)"
            params['q'] = f"%{search_query}%"
        sql += " ORDER BY patient_id ASC"
        patients = conn.execute(text(sql), params).mappings().all()
        return JsonResponse({'patients': [dict(row) for row in patients]})
 
@login_required
def get_patient_history_detail(request, patient_id):
    with engine.connect() as conn:
        # Lấy thông tin cá nhân - liệt kê rõ cột để tránh SELECT * trả về tên sai
        p_info = conn.execute(text("""
            SELECT patient_id, first_name, last_name, gender, date_of_birth,
                   contact_number, address, email, insurance_provider, insurance_number
            FROM patients WHERE patient_id = :id
        """), {"id": patient_id}).mappings().first()
 
        if not p_info:
            return JsonResponse({'error': 'Patient not found'}, status=404)
        
        # Lấy lịch sử khám + điều trị + hóa đơn (Join 3 bảng)
        history_sql = text("""
            SELECT 
                a.appointment_id, a.appointment_date, a.reason_for_visit, a.status,
                t.treatment_id, t.treatment_type, t.description, t.cost,
                b.bill_id, b.payment_status,
                d.first_name as doc_first, d.last_name as doc_last
            FROM appointments a
            LEFT JOIN treatments t ON a.appointment_id = t.appointment_id
            LEFT JOIN billing b ON t.treatment_id = b.treatment_id
            LEFT JOIN doctors d ON a.doctor_id = d.doctor_id
            WHERE a.patient_id = :id
            ORDER BY a.appointment_date DESC
        """)
        history = conn.execute(history_sql, {"id": patient_id}).mappings().all()
        
        return JsonResponse({
            'info': dict(p_info),
            'history': [dict(h) for h in history]
        })
    
def get_financial_report(request):
    period = request.GET.get('period', 'day')
    now = timezone.localtime(timezone.now())
    today_start = now.date() # Đây chính là biến bạn đang thiếu
    current_year = now.year

    if period == 'day':
        start_date = today_start
    elif period == 'week':
        # Đầu tháng hiện tại để tính các tuần trong tháng
        start_date = today_start.replace(day=1)
    elif period == 'month':
        # Đầu năm hiện tại để tính các tháng trong năm
        start_date = today_start.replace(month=1, day=1)
    else:
        start_date = today_start - timedelta(days=30)

    with engine.connect() as conn:
        # SQL tổng hợp doanh thu và số lượng ca khám
        query = text("""
            SELECT 
                COUNT(DISTINCT a.appointment_id) as total_appointments,
                COUNT(DISTINCT a.patient_id) as total_unique_patients,
                SUM(t.cost) as total_revenue,
                COUNT(t.treatment_id) as total_treatments
            FROM appointments a
            JOIN treatments t ON a.appointment_id = t.appointment_id
            JOIN billing b ON t.treatment_id = b.treatment_id
            WHERE b.payment_status = 'Paid' 
            AND a.appointment_date >= :start_date
        """)
        result = conn.execute(query, {"start_date": start_date}).mappings().first()
        
        # Lấy danh sách các khoản thu gần đây để hiển thị bảng
        trans_sql = text("""
            SELECT 
                a.appointment_date, 
                a.appointment_time,
                a.appointment_id, 
                a.patient_id, 
                a.doctor_id, 
                a.status
            FROM appointments a
            WHERE a.appointment_date >= :start_date
            ORDER BY a.appointment_date DESC
            LIMIT 10
        """)
        transactions = conn.execute(trans_sql, {"start_date": start_date}).mappings().all()
        formatted_transactions = []
        for t in transactions:
            d = dict(t)
            
            # Xử lý ngày khám
            d['appointment_date'] = d['appointment_date'].strftime('%d/%m/%Y') if d['appointment_date'] else 'N/A'
            
            # Xử lý giờ khám (Khắc phục lỗi timedelta)
            appt_time = d.get('appointment_time')
            if appt_time is not None:
                if isinstance(appt_time, timedelta):
                    # Chuyển đổi timedelta thành chuỗi HH:MM
                    total_seconds = int(appt_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    d['appointment_time'] = f"{hours:02d}:{minutes:02d}"
                elif hasattr(appt_time, 'strftime'):
                    d['appointment_time'] = appt_time.strftime('%H:%M')
                else:
                    d['appointment_time'] = str(appt_time)[:5] # Cắt lấy HH:MM từ chuỗi
            else:
                d['appointment_time'] = 'N/A'
                
            formatted_transactions.append(d)

        # Lấy specialization
        spec_sql = text("""
            SELECT d.specialization, COUNT(a.appointment_id) as count
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.doctor_id
            WHERE a.appointment_date >= :start_date
            GROUP BY d.specialization
        """)
        spec_results = conn.execute(spec_sql, {"start_date": start_date}).mappings().all()
        spec_labels = [row['specialization'] for row in spec_results]
        spec_values = [row['count'] for row in spec_results]

        # Lấy Trend
        if period == 'day':
            # Daily: Nhóm theo giờ của ngày hôm nay
            trend_sql = text("""
                SELECT HOUR(a.appointment_time) as label, SUM(t.cost) as revenue
                FROM appointments a
                JOIN treatments t ON a.appointment_id = t.appointment_id
                JOIN billing b ON t.treatment_id = b.treatment_id
                WHERE b.payment_status = 'Paid' AND a.appointment_date = :sd
                GROUP BY label ORDER BY label
            """)
            params = {"sd": now.date()}
        
        elif period == 'week':
            # Weekly: Hiện các ngày trong tuần này (Thứ 2 -> CN)
            start_of_week = now - timedelta(days=now.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            
            trend_sql = text("""
                SELECT a.appointment_date as label, SUM(t.cost) as revenue
                FROM appointments a
                JOIN treatments t ON a.appointment_id = t.appointment_id
                JOIN billing b ON t.treatment_id = b.treatment_id
                WHERE b.payment_status = 'Paid' 
                AND a.appointment_date BETWEEN :start AND :end
                GROUP BY label ORDER BY label
            """)
            params = {"start": start_of_week.date(), "end": end_of_week.date()}
            
        else: # period == 'month'
            # Monthly: Hiện các ngày trong tháng này (1 -> 30/31)
            first_day = now.replace(day=1)
            # Tìm ngày cuối cùng của tháng
            import calendar
            last_day_num = calendar.monthrange(now.year, now.month)[1]
            last_day = now.replace(day=last_day_num)
            
            trend_sql = text("""
                SELECT a.appointment_date as label, SUM(t.cost) as revenue
                FROM appointments a
                JOIN treatments t ON a.appointment_id = t.appointment_id
                JOIN billing b ON t.treatment_id = b.treatment_id
                WHERE b.payment_status = 'Paid' 
                AND a.appointment_date BETWEEN :start AND :end
                GROUP BY label ORDER BY label
            """)
            params = {"start": first_day.date(), "end": last_day.date()}

        trend_results = conn.execute(trend_sql, params).mappings().all()
        labels = []
        values = []

        for r in trend_results:
            if period == 'day':
                labels.append(f"{r['label']}h")
            else:
                # Format ngày thành dd/mm để hiển thị trên biểu đồ (VD: 11/05, 12/05...)
                # Vì r['label'] ở đây là đối tượng date từ MySQL
                labels.append(r['label'].strftime('%d/%m'))
            values.append(float(r['revenue'] or 0))

        #  Lấy status 
        status_sql = text("""
            SELECT 
                COUNT(DISTINCT CASE WHEN status = 'Completed' THEN appointment_id END) as completed, 
                COUNT(DISTINCT CASE WHEN status = 'Scheduled' THEN appointment_id END) as scheduled,
                COUNT(DISTINCT CASE WHEN status = 'No-show' THEN appointment_id END) as noshow,
                COUNT(DISTINCT CASE WHEN status = 'Cancelled' THEN appointment_id END) as cancelled
            FROM appointments
            WHERE appointment_date >= :start_date
        """)
        status_res = conn.execute(status_sql, {"start_date": start_date}).mappings().first()

    return JsonResponse({
        'summary': {
            'total_appointments': result['total_appointments'] or 0,
            'total_patients': result['total_unique_patients'] or 0, # Trả về số định danh duy nhất
            'total_revenue': float(result['total_revenue'] or 0),
        },
        'transactions': formatted_transactions, 
        'chart_data': {
            'status': {
                'completed': status_res['completed'] or 0,
                'scheduled': status_res['scheduled'] or 0,
                'noshow': status_res['noshow'] or 0,
                'cancelled': status_res['cancelled'] or 0
            },
            'specialization': {
                'labels': spec_labels,
                'values': spec_values},
            'trends': {'labels': labels, 'values': values}
        }
    })

# =====================================================================
# 4. LANDING PAGE
# =====================================================================

def home(request):
    """Trang chủ/Landing page của hệ thống."""
    return render(request, 'landing_page.html')