from django.db import models

class Appointment(models.Model):
    AppointmentID = models.AutoField(primary_key=True)
    DoctorID = models.CharField(max_length=10)
    PatientID = models.CharField(max_length=10)
    AppointmentDate = models.DateField()
    AppointmentTime = models.TimeField()

    class Meta:
        db_table = 'Appointments' 

class Patient(models.Model):
    PatientID = models.CharField(max_length=10, primary_key=True)
    FullName = models.CharField(max_length=100)
    # Thêm các trường khác nếu có...

    class Meta:
        db_table = 'Patients'