-- TẠO DATABASE 
CREATE DATABASE IF NOT EXISTS HospitalManagement; 
USE HospitalManagement; 

-- 2. TẠO BẢNG PATIENTS (Khớp với ảnh 4)
CREATE TABLE IF NOT EXISTS Patients (
    patient_id VARCHAR(10) PRIMARY KEY, 
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    gender ENUM('M', 'F', 'Other') NOT NULL, 
    date_of_birth DATE NOT NULL,
    contact_number VARCHAR(15),
    address VARCHAR(255), 
    registration_date DATE,
    insurance_provider VARCHAR(100),
    insurance_number VARCHAR(50),
    email VARCHAR(100) UNIQUE
); 

-- 3. TẠO BẢNG DOCTORS (Khớp với ảnh 3)
CREATE TABLE IF NOT EXISTS Doctors (
    doctor_id VARCHAR(10) PRIMARY KEY, 
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    specialization VARCHAR(100) NOT NULL, 
    phone_number VARCHAR(15),
    years_experience INT,
    hospital_branch VARCHAR(100),
    email VARCHAR(100) UNIQUE
); 

-- 4. TẠO BẢNG APPOINTMENTS (Khớp với ảnh 1)
CREATE TABLE IF NOT EXISTS Appointments (
    appointment_id VARCHAR(10) PRIMARY KEY, 
    patient_id VARCHAR(10) NOT NULL, 
    doctor_id VARCHAR(10) NOT NULL, 
    appointment_date DATE NOT NULL, 
    appointment_time TIME NOT NULL, 
    reason_for_visit VARCHAR(255),
    status ENUM('Scheduled', 'No-show', 'Cancelled', 'Completed') DEFAULT 'Scheduled',
    CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) 
        REFERENCES Patients(patient_id) ON DELETE CASCADE,
    CONSTRAINT fk_appt_doctor FOREIGN KEY (doctor_id) 
        REFERENCES Doctors(doctor_id) ON DELETE CASCADE
);

-- 5. TẠO BẢNG TREATMENTS (Khớp với ảnh 5)
CREATE TABLE IF NOT EXISTS Treatments (
    treatment_id VARCHAR(10) PRIMARY KEY,
    appointment_id VARCHAR(10) NOT NULL,
    treatment_type VARCHAR(100),
    description TEXT,
    cost DECIMAL(15, 2) NOT NULL CHECK (cost >= 0),
    treatment_date DATE,
    CONSTRAINT fk_treatment_appt FOREIGN KEY (appointment_id)
        REFERENCES Appointments(appointment_id) ON DELETE CASCADE
);

-- 6. TẠO BẢNG BILLS (Thay thế bảng Invoices - Khớp với ảnh 2)
CREATE TABLE IF NOT EXISTS Billing (
    bill_id VARCHAR(10) PRIMARY KEY, 
    patient_id VARCHAR(10) NOT NULL, 
    treatment_id VARCHAR(10) NOT NULL,
    bill_date DATE NOT NULL, 
    amount DECIMAL(15, 2) NOT NULL CHECK (amount >= 0), 
    payment_method VARCHAR(50), -- Ví dụ: Insurance, Credit Card
    payment_status ENUM('Pending', 'Paid', 'Failed') DEFAULT 'Pending',
    CONSTRAINT fk_bill_patient FOREIGN KEY (patient_id) 
        REFERENCES Patients(patient_id) ON DELETE CASCADE,
    CONSTRAINT fk_bill_treatment FOREIGN KEY (treatment_id)
        REFERENCES Treatments(treatment_id) ON DELETE CASCADE
);






