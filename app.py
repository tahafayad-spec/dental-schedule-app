import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import io

st.set_page_config(page_title="Dental College Auto-Scheduler", layout="wide")

st.title("🦷 Dental Clinical Supervision Auto-Scheduler")
st.write("Automate staff assignment considering attendance shifts, specialty roles, and slot capacities.")

# --- 1. STAFF MANAGEMENT ---
st.sidebar.header("1. Staff Roster (TAs & ALs)")
st.sidebar.info("Roles: 'TA' (covers all) or 'Assistant Lecturer' (fixed specialty).")

default_staff = pd.DataFrame([
    {"Name": "Dr. Ali Thabet", "Role": "TA", "Shift_Group": "Sat-Tue", "Specialty": "All", "Max_Slots_Day": 3},
    {"Name": "Dr. Fahmi", "Role": "TA", "Shift_Group": "Sat-Tue", "Specialty": "All", "Max_Slots_Day": 3},
    {"Name": "Dr. Zahraa Shawky", "Role": "TA", "Shift_Group": "Sat-Tue", "Specialty": "All", "Max_Slots_Day": 3},
    {"Name": "Dr. Rania", "Role": "Assistant Lecturer", "Shift_Group": "Sun-Wed", "Specialty": "Radiology", "Max_Slots_Day": 2},
    {"Name": "Dr. Ahmed", "Role": "Assistant Lecturer", "Shift_Group": "Mon-Thu", "Specialty": "Fixed Prosthodontics", "Max_Slots_Day": 2},
])

staff_df = st.sidebar.data_editor(default_staff, num_rows="dynamic", key="staff_editor")

# --- 2. CLINICS MANAGEMENT ---
st.header("2. Active Clinical Slots")

default_clinics = pd.DataFrame([
    {"Clinic_ID": "Endo_Sat_1", "Day": "Saturday", "Slot": "9-11", "Specialty": "Endodontics", "Required_Staff": 2},
    {"Clinic_ID": "Fixed_Sat_1", "Day": "Saturday", "Slot": "9-11", "Specialty": "Fixed Prosthodontics", "Required_Staff": 2},
    {"Clinic_ID": "Radio_Sun_1", "Day": "Sunday", "Slot": "11-1", "Specialty": "Radiology", "Required_Staff": 1},
    {"Clinic_ID": "Fixed_Mon_1", "Day": "Monday", "Slot": "1-3", "Specialty": "Fixed Prosthodontics", "Required_Staff": 1},
])

clinics_df = st.data_editor(default_clinics, num_rows="dynamic", key="clinic_editor")

# --- 3. SOLVER ENGINE ---
st.header("3. Generate Schedule")

shift_mapping = {
    "Sat-Tue": ["Saturday", "Sunday", "Monday", "Tuesday"],
    "Sun-Wed": ["Sunday", "Monday", "Tuesday", "Wednesday"],
    "Mon-Thu": ["Monday", "Tuesday", "Wednesday", "Thursday"]
}

if st.button("🚀 Auto-Generate Schedule", type="primary"):
    model = cp_model.CpModel()
    
    staff_list = staff_df.to_dict('records')
    clinic_list = clinics_df.to_dict('records')
    
    # Variables
    assignments = {}
    for s_idx, s in enumerate(staff_list):
        for c_idx, c in enumerate(clinic_list):
            assignments[(s_idx, c_idx)] = model.NewBoolVar(f"assign_{s_idx}_{c_idx}")
            
            # Constraint 1: Attendance Shift Match
            allowed_days = shift_mapping.get(s["Shift_Group"], [])
            if c["Day"] not in allowed_days:
                model.Add(assignments[(s_idx, c_idx)] == 0)
                
            # Constraint 2: Specialty Lock for Assistant Lecturers
            if s["Role"] == "Assistant Lecturer" and s["Specialty"] != "All" and s["Specialty"] != c["Specialty"]:
                model.Add(assignments[(s_idx, c_idx)] == 0)

    # Constraint 3: Required Staffing Per Clinic
    for c_idx, c in enumerate(clinic_list):
        model.Add(sum(assignments[(s_idx, c_idx)] for s_idx in range(len(staff_list))) == int(c["Required_Staff"]))

    # Constraint 4: No Double Booking
    days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    slots = ["9-11", "11-1", "1-3", "3-5"]
    
    for s_idx in range(len(staff_list)):
        for day in days:
            for slot in slots:
                overlapping = [c_idx for c_idx, c in enumerate(clinic_list) if c["Day"] == day and c["Slot"] == slot]
                if overlapping:
                    model.Add(sum(assignments[(s_idx, c_idx)] for c_idx in overlapping) <= 1)

    # Constraint 5: Daily Workload Cap
    for s_idx, s in enumerate(staff_list):
        for day in days:
            day_clinics = [c_idx for c_idx, c in enumerate(clinic_list) if c["Day"] == day]
            if day_clinics:
                model.Add(sum(assignments[(s_idx, c_idx)] for c_idx in day_clinics) <= int(s["Max_Slots_Day"]))

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        st.success("✅ Schedule Generated Successfully!")
        
        results = []
        for c_idx, c in enumerate(clinic_list):
            assigned_names = [
                f"{staff_list[s_idx]['Name']} ({staff_list[s_idx]['Role']})"
                for s_idx in range(len(staff_list))
                if solver.Value(assignments[(s_idx, c_idx)]) == 1
            ]
            results.append({
                "Day": c["Day"],
                "Slot": c["Slot"],
                "Clinic ID": c["Clinic_ID"],
                "Specialty": c["Specialty"],
                "Assigned Staff": ", ".join(assigned_names)
            })
            
        res_df = pd.DataFrame(results)
        st.dataframe(res_df, use_container_width=True)
        
        # Excel Export Button
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            res_df.to_excel(writer, index=False, sheet_name='Supervision Schedule')
            
        st.download_button(
            label="📥 Download Schedule as Excel",
            data=buffer.getvalue(),
            file_name="clinical_supervision_schedule.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ No feasible schedule found with current staff constraints. Try increasing available staff or relaxing workload limits.")
