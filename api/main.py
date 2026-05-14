import os 
from final_sql.api.manager_functions import * 

def clear_screen(): 
    # Clear terminal screen based on OS 
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(): 
    print("\n" + "="*50)
    print ("HOSPITAL MANAGEMENT SYSTEM (V1.0)")
    print("="*50)

def main_menu(): 
    while True: 
        print_header()
        print("1. [patient] Register New Patient")
        print("2. [Search]  Find Patient by Name")
        print("3. [Medical] View Patient Medical History")
        print("4. [Finance] Get Daily Revenue Report")
        print("5. [Stats]   View Doctor Workload Analytics")
        print("0. [Exit]    Close Application")
        print("-" * 50)

        choice = input("Please select an option (0-5): ")

        if choice == '1':
            print("\n--- Register New Patient ---")
            p_id = input("Enter Patient ID (e.g., P001): ")
            name = input("Enter Full Name: ")
            gender = input("Enter Gender (M/F): ").upper()
            dob = input("Enter Date of Birth (YYYY-MM-DD): ")
            phone = input("Enter Phone Number: ")
            address = input("Enter Address: ")
            add_new_patient(p_id, name, gender, dob, phone, address)

        elif choice == '2':
            print("\n--- Search Patient ---")
            name = input("Enter n8ame to search: ")
            find_patient_by_name(name)

        elif choice == '3':
            print("\n--- Patient Medical History ---")
            p_id = input("Enter Patient ID: ")
            get_patient_medical_history(p_id)

        elif choice == '4':
            print("\n--- Daily Revenue Report ---")
            date = input("Enter date (YYYY-MM-DD): ")
            get_daily_revenue(date)

        elif choice == '5':
            get_doctor_workload()

        elif choice == '0':
            print("\nShutting down system... Goodbye!")
            break
        
        else:
            print("\n>>> INVALID OPTION: Please try again.")
        
        input("\nPress Enter to return to menu...")
        clear_screen()

if __name__ == "__main__":
    main_menu()