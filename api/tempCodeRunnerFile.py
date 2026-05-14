import os
import pandas as pd
from sqlalchemy import text
from connect_database import engine

def insert_all_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    excel_file_name = 'data_final.xlsx'
    
    excel_path = next((os.path.join(d, excel_file_name) for d in [current_dir, parent_dir] if os.path.exists(os.path.join(d, excel_file_name))), None)

    if not excel_path:
        print(f">>> LỖI: Không tìm thấy file {excel_file_name}!")
        return

    xl = pd.ExcelFile(excel_path)
    actual_sheets = xl.sheet_names
    
    # Mapping đúng tên sheet và tên bảng của bạn
    mapping = [
        ('patients', 'Patients', ['patient_id', 'first_name', 'last_name', 'gender', 'date_of_birth', 'contact_number', 'address', 'registration_date', 'insurance_provider', 'insurance_number', 'email']),
        ('doctors', 'Doctors', ['doctor_id', 'first_name', 'last_name', 'specialization', 'phone_number', 'years_experience', 'hospital_branch', 'email']),
        ('appointments', 'Appointments', ['appointment_id', 'patient_id', 'doctor_id', 'appointment_date', 'appointment_time', 'reason_for_visit', 'status']),
        ('treatments', 'Treatments', ['treatment_id', 'appointment_id', 'treatment_type', 'description', 'cost', 'treatment_date']),
        ('billing', 'Billing', ['bill_id', 'patient_id', 'treatment_id', 'bill_date', 'amount', 'payment_method', 'payment_status'])
    ]

    with engine.connect() as conn:
        print("--- ĐANG TẮT KIỂM TRA RÀNG BUỘC ĐỂ NẠP TOÀN BỘ DỮ LIỆU ---")
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        # Nếu muốn xóa sạch để nạp mới hoàn toàn (Tránh lỗi trùng Primary Key)
        for _, table_name, _ in mapping:
            conn.execute(text(f"TRUNCATE TABLE {table_name};"))
        
        for sheet_keyword, table_name, columns in mapping:
            sheet_name = next((s for s in actual_sheets if sheet_keyword.lower() in s.lower()), None)
            
            if sheet_name:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet_name)
                    df.columns = [str(c).strip().lower() for c in df.columns]
                    
                    # Giữ nguyên toàn bộ dữ liệu, chỉ lấy đúng cột
                    existing_cols = [c for c in columns if c in df.columns]
                    data_to_insert = df[existing_cols]

                    # Nạp vào database
                    data_to_insert.to_sql(table_name, con=engine, if_exists='append', index=False)
                    print(f">>> XONG: Bảng {table_name} đã nạp {len(data_to_insert)} dòng.")
                
                except Exception as e:
                    print(f">>> LỖI tại bảng {table_name}: {e}")
            else:
                print(f">>> Bỏ qua: Không thấy sheet '{sheet_keyword}'")

        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        conn.commit()
        print("--- ĐÃ HOÀN THÀNH NẠP DỮ LIỆU ---")

if __name__ == "__main__":
    insert_all_data()