# HT Hospital – Hospital Management System

A web-based hospital management system built with **Django (Python)** and **SQL Server**, designed to streamline hospital operations including patient management, appointment scheduling, and administrative tasks.

---

# Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Running the Project](#running-the-project)
- [Project Structure](#project-structure)
---

## Features

- Patient registration and management
- Appointment scheduling
- Doctor and staff management
- Medical records management
- Administrative dashboard
- User authentication and role-based access

---

## 🛠️ Tech Stack

| Layer      | Technology              |
|------------|-------------------------|
| Backend    | Python 3.10, Django     |
| Database   | SQL Server              |
| Frontend   | HTML, CSS (Django Templates) |
| ORM        | Django ORM + raw SQL    |

---

## Prerequisites

Make sure you have the following installed:

- Python 3.10+
- pip
- SQL Server (or SQL Server Express)
- ODBC Driver for SQL Server

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/ThucNhi123/HT-Hospital-Hospital-Management-.git
cd HT-Hospital-Hospital-Management-
```

**2. Create and activate a virtual environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Database Setup

**1. Run the SQL scripts in order:**

```
SQL/CreateDatabase.sql       ← Create the database schema
SQL/AdvancedDatabase.sql     ← Insert advanced/seed data
```

Open SQL Server Management Studio (SSMS) or any SQL client, connect to your server, then execute the scripts in the order above.

**2. Configure the database connection**

Update `api/connect_database.py` (or `final_sql/settings.py`) with your SQL Server credentials:

```python
# Example connection string
SERVER   = 'your_server_name'
DATABASE = 'HT_Hospital'
USERNAME = 'your_username'
PASSWORD = 'your_password'
```

**3. Apply Django migrations**

```bash
python manage.py migrate
```

*(Optional)* Insert sample data:

```bash
python api/insert_data.py
```

---

## Running the Project

```bash
python manage.py runserver
```

Then open your browser and navigate to:

```
http://127.0.0.1:8000/
```

---

## Project Structure

```
HT-Hospital/
├── SQL/
│   ├── CreateDatabase.sql       # Database schema
│   └── AdvancedDatabase.sql     # Seed / advanced data
│
├── api/                         # Main application
│   ├── templates/               # HTML templates
│   ├── static/                  # CSS, images, assets
│   ├── migrations/              # Django migrations
│   ├── models.py                # Data models
│   ├── views.py                 # View logic
│   ├── urls.py                  # URL routing
│   ├── forms.py                 # Django forms
│   ├── manager_functions.py     # Business logic
│   ├── connect_database.py      # DB connection config
│   └── insert_data.py           # Data seeding script
│
├── final_sql/                   # Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── manage.py
├── requirements.txt
└── README.md
```

---

##  Contributing

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

