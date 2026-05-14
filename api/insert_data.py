import os
import pandas as pd
from sqlalchemy import text
from connect_database import engine

def insert_final_version():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    excel_file_name = 'data_final.xlsx'
    excel_path = next((os.path.join(d, excel_file_name) for d in [current_dir, parent_dir] if os.path.exists(os.path.join(d, excel_file_name))), None)

    if not excel_path:
        print(f">>> LỖI: Không tìm thấy file {excel_file_name}!")
        return

    xl = pd.ExcelFile(excel_path)
    actual_sheets = xl.sheet_names

    mapping = [
        ('patients', 'Patients', ['patient_id', 'first_name', 'last_name', 'gender', 'date_of_birth', 'contact_number', 'address', 'registration_date', 'insurance_provider', 'insurance_number', 'email']),
        ('doctors', 'Doctors', ['doctor_id', 'first_name', 'last_name', 'specialization', 'phone_number', 'years_experience', 'hospital_branch', 'email']),
        ('appointments', 'Appointments', ['appointment_id', 'patient_id', 'doctor_id', 'appointment_date', 'appointment_time', 'reason_for_visit', 'status']),
        ('treatments', 'Treatments', ['treatment_id', 'appointment_id', 'treatment_type', 'description', 'cost', 'treatment_date']),
        ('billing', 'Billing', ['bill_id', 'patient_id', 'treatment_id', 'bill_date', 'amount', 'payment_method', 'payment_status'])
    ]

    # Dùng context manager để đảm bảo kết nối luôn đóng sau khi xong
    with engine.connect() as conn:
        trans = conn.begin() # Bắt đầu một giao dịch (transaction)
        try:
            print("--- CHẾ ĐỘ NẠP BẤT CHẤP: ĐANG TẮT RÀNG BUỘC ---")
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))

            for sheet_keyword, table_name, columns in mapping:
                sheet_name = next((s for s in actual_sheets if sheet_keyword.lower() in s.lower()), None)
                
                if sheet_name:
                    df = pd.read_excel(excel_path, sheet_name=sheet_name)
                    df.columns = [str(c).strip().lower() for c in df.columns]
                    
                    # Lọc trùng Primary Key (BẮT BUỘC vì SQL không bao giờ cho trùng ID)
                    # Chúng ta lấy cột đầu tiên làm ID để lọc
                    id_col = columns[0] 
                    if id_col in df.columns:
                        df = df.drop_duplicates(subset=[id_col])
                    
                    # Riêng bảng Patients, lọc thêm email trùng để tránh lỗi 1062
                    if table_name == 'Patients' and 'email' in df.columns:
                        df = df.drop_duplicates(subset=['email'])

                    existing_cols = [c for c in columns if c in df.columns]
                    
                    # Nạp dữ liệu (if_exists='append' vì đã truncate ở ngoài hoặc muốn nạp đè)
                    # Nếu muốn nạp sạch từ đầu, hãy dùng 'replace' hoặc chạy lệnh TRUNCATE trước
                    df[existing_cols].to_sql(table_name, con=conn, if_exists='append', index=False)
                    print(f">>> THÀNH CÔNG: Bảng {table_name} đã nạp {len(df)} dòng.")
                else:
                    print(f">>> BỎ QUA: Không tìm thấy sheet '{sheet_keyword}'")

            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            trans.commit() # Xác nhận lưu mọi thay đổi
            print("--- HOÀN THÀNH: TẤT CẢ DỮ LIỆU ĐÃ VÀO DATABASE ---")
            
        except Exception as e:
            trans.rollback() # Nếu có lỗi nặng, quay lại trạng thái cũ
            print(f">>> LỖI NGHIÊM TRỌNG: {e}")

if __name__ == "__main__":
    # TRƯỚC KHI CHẠY: Bạn nên chạy các lệnh TRUNCATE trong SQL Workbench để làm sạch máy
    insert_final_version()