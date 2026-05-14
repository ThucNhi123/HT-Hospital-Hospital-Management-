-- Tìm kiếm tên bệnh nhân (dùng concat vì đã tách first/last name)
CREATE INDEX idx_patient_name ON Patients(last_name, first_name); 

-- Lọc lịch theo ngày hẹn
CREATE INDEX idx_appointment_date ON Appointments(appointment_date);

-- Tìm kiếm nhanh qua số điện thoại
CREATE INDEX idx_patient_phone ON Patients(contact_number);

-- Lọc bác sĩ theo chuyên khoa
CREATE INDEX idx_doctor_specialty ON Doctors(specialization);

-- Kiểm tra lịch trống của bác sĩ theo ngày (Composite Index)
CREATE INDEX idx_appt_doctor_date ON Appointments(doctor_id, appointment_date);

-- View dành cho Tiếp tân
CREATE VIEW View_dailyAppointments AS 
SELECT 
    a.appointment_id, 
    CONCAT(p.first_name, ' ', p.last_name) AS patient_name, 
    CONCAT(d.first_name, ' ', d.last_name) AS doctor_name, 
    a.appointment_time
FROM Appointments a 
JOIN Patients p ON a.patient_id = p.patient_id 
JOIN Doctors d ON a.doctor_id = d.doctor_id 
WHERE a.appointment_date = CURDATE();

-- View: Lịch khám trong ngày của bác sĩ
CREATE VIEW View_DoctorSchedule AS
SELECT 
    CONCAT(d.first_name, ' ', d.last_name) AS doctor_name,
    CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
    a.appointment_time,
    a.appointment_date
FROM Appointments a
JOIN Doctors d ON a.doctor_id = d.doctor_id
JOIN Patients p ON a.patient_id = p.patient_id
WHERE a.appointment_date = CURDATE();

-- View: Doanh thu theo chuyên khoa (Dựa trên bảng Bills và Doctors)
CREATE VIEW View_DepartmentPerformance AS
SELECT 
    d.specialization AS Department,
    COUNT(DISTINCT b.bill_id) AS TotalVisits,
    SUM(b.amount) AS TotalRevenue
FROM Doctors d
JOIN Appointments a ON d.doctor_id = a.doctor_id
JOIN Billing b ON a.patient_id = b.patient_id AND a.appointment_date = b.bill_date
WHERE MONTH(b.bill_date) = MONTH(CURDATE()) AND YEAR(b.bill_date) = YEAR(CURDATE())
GROUP BY d.specialization;

-- View: Danh sách bệnh nhân thân thiết (Khám trên 3 lần/năm)
CREATE VIEW View_LoyalPatients AS
SELECT 
    CONCAT(p.first_name, ' ', p.last_name) AS patient_name, 
    p.contact_number, 
    COUNT(a.appointment_id) AS VisitCount
FROM Patients p
JOIN Appointments a ON p.patient_id = a.patient_id
WHERE YEAR(a.appointment_date) = YEAR(CURDATE())
GROUP BY p.patient_id
HAVING VisitCount >= 3;


-- Thủ tục đặt lịch có kiểm tra trùng giờ
DELIMITER //
CREATE PROCEDURE sp_BookAppointment(
    IN p_aid VARCHAR(10),
    IN p_pid VARCHAR(10),
    IN p_did VARCHAR(10),
    IN p_date DATE,
    IN p_time TIME,
    IN p_reason TEXT 
)
BEGIN
    -- Kiểm tra xem bác sĩ có bận không (giữ nguyên logic cũ của bạn)
    IF EXISTS (SELECT 1 FROM Appointments 
               WHERE doctor_id = p_did 
               AND appointment_date = p_date 
               AND appointment_time = p_time
               AND status = 'Scheduled') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: The doctor is already booked';
    ELSE
        -- Insert với lý do khám và trạng thái mặc định
        INSERT INTO Appointments (appointment_id, patient_id, doctor_id, appointment_date, appointment_time, reason_for_visit, status)
        VALUES (p_aid, p_pid, p_did, p_date, p_time, p_reason, 'Scheduled');
    END IF;
END //
DELIMITER ;

-- Thủ tục hủy lịch hẹn
DELIMITER //
CREATE PROCEDURE sp_CancelAppointment(IN p_ApptID VARCHAR(10), OUT p_Message VARCHAR(100))
BEGIN
    IF EXISTS (SELECT 1 FROM Appointments WHERE appointment_id = p_ApptID) THEN
        UPDATE Appointments SET status = 'Cancelled' WHERE appointment_id = p_ApptID;
        SET p_Message = 'Cancellation Successful';
    ELSE
        SET p_Message = 'Error: Appointment not found';
    END IF;
END //

DELIMITER ;

DELIMITER //

-- Trigger: Kiểm tra ngày sinh (Không được ở tương lai)
CREATE TRIGGER trg_CheckAge
BEFORE INSERT ON Patients
FOR EACH ROW
BEGIN
    IF NEW.date_of_birth > CURDATE() THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Date of Birth cannot be in the future';
    END IF;
END //

-- Trigger: Chặn bác sĩ nhận quá 20 lịch hẹn/ngày
CREATE TRIGGER trg_CapacityCheck
BEFORE INSERT ON Appointments
FOR EACH ROW
BEGIN
    DECLARE appt_count INT;
    SELECT COUNT(*) INTO appt_count FROM Appointments 
    WHERE doctor_id = NEW.doctor_id AND appointment_date = NEW.appointment_date;
    
    IF appt_count >= 20 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Error: Doctor capacity reached (max 20/day)';
    END IF;
END //

DELIMITER ;






