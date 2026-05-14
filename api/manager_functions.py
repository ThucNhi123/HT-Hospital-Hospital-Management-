import pandas as pd 
from .connect_database import engine 
from sqlalchemy import text

# ============ PATIENT MANAGEMENT ===========
def add_new_patient(patient_id, name, gender, dob, phone, address):
    """
    Add a new patient with data validation.
    Cấu trúc mới: first_name, last_name (tạm gộp vào first_name), contact_number, date_of_birth.
    """

    # 1. Check if phone number is valid
    if not str(phone).isdigit() or len(str(phone)) < 10:
        print(">>> ERROR: Invalid phone number format! (Must be digits and >= 10 chars)")
        return 

    # 2. Execute insert (Mapping với snake_case)
    query = text("""
        INSERT INTO Patients (patient_id, first_name, last_name, gender, date_of_birth, contact_number, address)
        VALUES (:id, :name, '', :gender, :dob, :phone, :address)         
    """)

    try: 
        with engine.connect() as conn: 
            conn.execute(query, {
                "id": patient_id, "name": name, "gender": gender, 
                "dob": dob, "phone": phone, "address": address
            })
            conn.commit()
            print(f">>> SUCCESS: Patient '{name}' has been added to the database.")
    except Exception as e: 
        if "1062" in str(e):
            print(f">>> ERROR: Duplicate entry! Patient ID or Contact Number already exists.")
        elif "CheckAge" in str(e) or "trigger" in str(e).lower():
            print(f">>> TRIGGER ERROR: Invalid Date of Birth! (Cannot be in the future).")
        else:
            print(f">>> DATABASE ERROR: {e}")

# ============ SEARCH FUNCTION ============
def find_patient_by_name(search_name): 
    """
    Search for patients by name.
    Optimised by "Index on first_name, last_name"
    """
    query = text("SELECT * FROM Patients WHERE first_name LIKE :name OR last_name LIKE :name")
    try: 
        with engine.connect() as conn: 
            df = pd.read_sql(query, conn, params={"name": f"%{search_name}%"})

        if not df.empty: 
            print(f">>> FOUND {len(df)} records for '{search_name}'")
            print(df.to_string(index=False))
        else: 
            print(f"\n>>> NO RESULTS: No patients found with the name '{search_name}'.")
    except Exception as e: 
        print(f">>> SEARCH ERROR: {e}")

# ============ DAILY REVENUE REPORT ============
def get_daily_revenue(target_date): 
    """Calculates total revenue from Billing table"""
    query = text("SELECT SUM(amount) as DailyTotal FROM Billing WHERE bill_date = :date")
    try: 
        with engine.connect() as conn: 
            result = conn.execute(query, {"date": target_date}).fetchone()
            total = result[0] if result[0] else 0
            print(f">>> REPORT: Total Revenue for {target_date} is ${total:,.2f}")
            return total 
    except Exception as e:
        print(f">>> REPORT ERROR: {e}")

# ============ DOCTOR WORKLOAD ANALYTICS ============
def get_doctor_workload():
    """Shows how many appointments each doctor has"""
    query = text("""
        SELECT 
            CONCAT(d.first_name, ' ', d.last_name) AS doctor_name, 
            d.specialization, 
            COUNT(a.appointment_id) AS total_appointments
        FROM Doctors d 
        LEFT JOIN Appointments a ON d.doctor_id = a.doctor_id
        GROUP BY d.doctor_id, d.first_name, d.last_name, d.specialization
        ORDER BY total_appointments DESC
    """)

    try: 
        with engine.connect() as conn: 
            df = pd.read_sql(query, conn)
        
        print("\n" + "="*40)
        print("--- DOCTOR WORKLOAD REPORT ---")
        print("\n" + "="*40)

        if not df.empty:
            print(df.to_string(index=False))
            max_workload = df.iloc[0]
            print(f"\n>>> INSIGHT: Doctor {max_workload['doctor_name']} is the busiest with {max_workload['total_appointments']} appointments.")
        else: 
            print(f">>> NO DATA: No doctors or appointments found.")
    except Exception as e: 
        print(f">>> ANALYTICS ERROR: {e}")

# ============ MEDICAL HISTORY ============
def get_patient_medical_history(patient_id): 
    """Cập nhật để lấy thêm Reason, Status, Treatment Type và Description"""
    query = text("""
        SELECT 
            a.appointment_id, 
            a.appointment_date, 
            a.appointment_time, 
            CONCAT(d.first_name, ' ', d.last_name) AS doctor_name, 
            d.specialization,
            a.reason_for_visit,
            a.status,
            t.treatment_type,
            t.description AS treatment_description
        FROM Appointments a
        JOIN Doctors d ON a.doctor_id = d.doctor_id
        LEFT JOIN Treatments t ON a.appointment_id = t.appointment_id
        WHERE a.patient_id = :pid
        ORDER BY a.appointment_date DESC
    """)
    try: 
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"pid": patient_id})
        
        if not df.empty:
            return df.to_dict(orient='records')
        else: 
            return []
    except Exception as e: 
        print(f">>> HISTORY ERROR: {e}")
        return []

# ============ BOOK APPOINTMENT ============
def generate_next_appointment_id():
    # Tìm mã ID lớn nhất hiện có trong bảng Appointments
    query = text("SELECT appointment_id FROM Appointments WHERE appointment_id LIKE 'A%' ORDER BY appointment_id DESC LIMIT 1")
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query).scalar()
            
            if result:
                # Giả sử result là 'A200'
                # Tách lấy phần số sau chữ 'A'
                current_number = int(result[1:]) 
                new_number = current_number + 1
                # Trả về mã mới, dùng zfill(3) để đảm bảo có ít nhất 3 chữ số (A201, A202...)
                return f"A{str(new_number).zfill(3)}"
            else:
                # Nếu bảng trống, bắt đầu từ A001
                return "A001"
    except Exception as e:
        print(f"Lỗi tạo ID: {e}")
        return "A999" # Mã dự phòng nếu lỗi
    
def book_appointment(patient_id, doctor_id, appt_date, appt_time, reason):
    """
    Cập nhật đặt lịch: Thêm lý do khám và mặc định trạng thái Scheduled.
    """
    new_appt_id = generate_next_appointment_id()

    # Lưu ý: Mình giả định Procedure của bạn đã được thêm cột reason_for_visit
    query = text("CALL sp_BookAppointment(:aid, :pid, :did, :adate, :atime, :reason)")
    
    try:
        with engine.connect() as conn:
            conn.execute(query, {
                "aid": new_appt_id,
                "pid": patient_id, 
                "did": doctor_id, 
                "adate": appt_date, 
                "atime": appt_time,
                "reason": reason  # Truyền lý do từ form vào đây
            })
            conn.commit()
            print(f">>> SUCCESS: Appointment {new_appt_id} booked successfully.")
            return True
    except Exception as e:
        if "already booked" in str(e).lower():
            print(">>> BOOKING ERROR: The doctor is not available at this time.")
        else:
            print(f">>> DATABASE ERROR: {e}")
        return False

# ============ GET DOCTOR LIST FROM DTB ============
def get_all_doctors():
    # Cập nhật query để lấy thêm kinh nghiệm, chi nhánh và email
    query = text("""
        SELECT 
            doctor_id, 
            CONCAT(first_name, ' ', last_name) AS doctor_name, 
            specialization,
            years_experience, 
            hospital_branch,
            email
        FROM Doctors
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(query).mappings().all()
            return [dict(row) for row in result]
    except Exception as e:
        print(f"Error fetching doctors: {e}")
        return []