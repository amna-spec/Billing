# Description: This file contains the main logic for the Streamlit app.
import streamlit as st
from datetime import datetime, timedelta
import os
from functions import *
import pandas as pd
import sqlite3

conn = get_connection()
cursor = conn.cursor()
# Streamlit UI 
st.set_page_config(page_title="Electricity Billing System", layout="wide")
st.sidebar.title("⚡ Electricity Billing System")
st.sidebar.markdown("---")  # Add a separator

# Define a single menu variable
menu_options = {
    "👤 User Management": {
        "User Operations": ["Add User", "Update User", "Delete User"],
        "📊 Report Logs": ["User Directory"]
    },
    "📊 Billing Management": {
        "Billing Operations": ["Enter Bill Record", "Update/Delete Bill Record"],
        "Billing Actions": ["Generate Bill"],
        "📊 Report Logs": ["Billing Records"]
    },
    "⚡ Rate Management": {
        "Rate Operations": ["Insert/Update Rates", "View Rates"]
    }
}

# Sidebar navigation
st.sidebar.title("📌 Main Menu")
# Sidebar for menu selection
selected_section = st.sidebar.radio("Select Section", list(menu_options.keys()))

# Get the submenu based on selected section
submenu_options = []
for category, options in menu_options[selected_section].items():
    submenu_options.extend(options)

# Create radio button for menu selection
selected_option = st.sidebar.radio("Menu", submenu_options)

st.sidebar.markdown("---")  # Add a separator

# Main logic
# User Management
if selected_section == "👤 User Management":
    if selected_option == "Add User":
        st.title("➕ Add New User")
        person_id = st.text_input("Person ID")
        name = st.text_input("Name")
        flat_no = st.text_input("Flat No")
        user_type = st.selectbox("User Type", ["Residential", "Commercial"], index=0)
        load_sanctioned = st.number_input("Load Sanctioned (kW)", min_value=0.0, step=0.1)
        phase = st.selectbox("Phase", ["1-Phase", "3-Phase"], index=0)
        if st.button("✅ Add User"):
            insert_user(person_id, name, flat_no, user_type, load_sanctioned, phase)
            st.success("User added successfully!")

    # Update or Delete User
    elif selected_option == "Update User" or selected_option == "Delete User":
        st.title("✏️ Update or 🗑️ Delete User")
        # Placeholder for fetching users
        users_df = get_table_data("Users")
        if not users_df.empty:
            selected_user_id = st.selectbox("Select a User ID", users_df["PersonID"].tolist())
            user_data = users_df[users_df["PersonID"] == selected_user_id].iloc[0]
            name = st.text_input("Name", user_data["Name"])
            flat_no = st.text_input("Flat No", user_data["FlatNo"])
            user_type = st.selectbox("User Type", ["Residential", "Commercial"], index=["Residential", "Commercial"].index(user_data["UserType"]))
            load_sanctioned = st.number_input("Load Sanctioned (kW)", min_value=0.0, step=0.1, value=float(user_data["LoadSanctioned"]))
            phase = st.selectbox("Phase", ["1-Phase", "3-Phase"], index=["1-Phase", "3-Phase"].index(user_data["Phase"]))
            
            if selected_option == "Update User" and st.button("✏️ Update User"):
                update_user(selected_user_id, name, flat_no, user_type, load_sanctioned, phase)
                st.success("User updated successfully!")
            elif selected_option == "Delete User" and st.button("🗑️ Delete User"):
                delete_user(selected_user_id)
                st.warning("User deleted!")
        else:
            st.warning("No users found!")

    # Report Logs to view all users and allow searching by person ID and name
    elif selected_option == "User Directory":
        st.title("📜 User Directory")

        # Fetch Users Data
        users_df = get_table_data("Users")

        if not users_df.empty:
            st.write("### 🔍 Search Users (Optional)")
            col1, col2 = st.columns(2)

            with col1:
                person_id_filter = st.text_input("Search by Person ID (exact match):", key="person_id")
            with col2:
                name_filter = st.text_input("Search by Name (contains, case-insensitive):", key="name")

            # Initialize filtered DataFrame with all users
            filtered_users_df = users_df.copy()

            # Apply search filters if provided
            if person_id_filter:
                filtered_users_df = filtered_users_df[filtered_users_df["PersonID"].astype(str) == person_id_filter]
            if name_filter:
                filtered_users_df = filtered_users_df[filtered_users_df["Name"].str.contains(name_filter, case=False, na=False)]

            # Display full dataset or filtered results
            if filtered_users_df.empty:
                st.warning("No users found matching your search criteria.")
            else:
                st.write(f"### Users ({len(filtered_users_df)} records found)")
                st.dataframe(filtered_users_df.sort_values(by="Name"))

            # Download Option
            st.download_button("📥 Download CSV", filtered_users_df.to_csv(index=False), "users.csv", "text/csv")

        else:
            st.warning("No users available!")

# Handling Billing Management section
elif selected_section == "📊 Billing Management":
    if selected_option == "Enter Bill Record":
        st.title("📋 Insert Billing Data")

        # Fetch necessary data
        users_df = get_table_data("Users")
        flats_df = get_table_data("Flats")
        gst_rates_df = get_table_data("GSTRates")
        duty_rates_df = get_table_data("ElectricDutyRates")
        surcharge_types_df = get_surcharge_rates()
        
        # Select user and flat
        person_id = st.selectbox("Select Person ID", users_df["PersonID"].tolist())
        selected_user = users_df[users_df["PersonID"] == person_id].iloc[0]
        flat_no = st.selectbox("Select Flat No", flats_df[flats_df["FlatNo"].isin([selected_user["FlatNo"]])]["FlatNo"].tolist())
        user_category = users_df.loc[users_df["PersonID"] == person_id, "UserCategory"].iloc[0]
        name = users_df.loc[users_df["PersonID"] == person_id, "Name"]

        if not name.empty:
         name = name.iloc[0]  # Extract the first value safely
        else:
         name = "Unknown"  # Default value if no match found


        # Select Billing Month (format: YYYY-MM)
        current_year = datetime.now().year
        month_mapping = {m: f"{current_year}-{i:02d}" for i, m in enumerate([
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"], 1)}
        selected_month = st.selectbox("Billing Month", list(month_mapping.keys()))
        billing_month = month_mapping[selected_month]

        # Meter Reading Inputs
        present_reading = st.number_input("Present Reading (kWh)", min_value=0.0, step=0.01)
        previous_month = get_previous_month(billing_month)
        reading_id=0
        # Fetch previous reading
        cursor.execute("""  
        SELECT PresentReading FROM BillingReadings 
        WHERE FlatNo = ? AND BillingMonth = ? 
        ORDER BY BillingMonth DESC LIMIT 1
        """, (flat_no, previous_month))
        previous_reading = cursor.fetchone()
        previous_reading = previous_reading[0] if previous_reading else 0.0  
        # Ensure session state for reading_id 
        if "fetched_reading_id" not in st.session_state:
          st.session_state.fetched_reading_id = None 
        # Calculate units consumed
        units_consumed = calculate_units_consumed(previous_reading, present_reading)
        if st.button("📌 Insert Reading"):
            try:
                fetched_reading_id=insert_reading(cursor,conn,flat_no, previous_reading, present_reading)
                # Fetch last inserted ID and store it
                if fetched_reading_id is not None and fetched_reading_id > 0:
                  st.session_state.fetched_reading_id = fetched_reading_id
                  st.success(f"✅ Reading inserted! ID: {st.session_state.fetched_reading_id}")

                       
            except sqlite3.Error as e:
                st.error(f"Database Error: {e}")
           # GST Selection
        if "fetched_reading_id" in st.session_state and st.session_state.fetched_reading_id:
              st.subheader("💰 Additional Charges")
              gst_options = gst_rates_df["GST"].tolist() if not gst_rates_df.empty else []
              gst_selected = st.selectbox("Select GST (%)", gst_options + ["Manual Entry"], index=0)
              gst_value = st.number_input("Enter GST (%)", min_value=0.0, step=0.01) if gst_selected == "Manual Entry" else gst_selected

             # Electric Duty Selection
              duty_options = duty_rates_df["ElectricDuty"].tolist() if not duty_rates_df.empty else []
              duty_selected = st.selectbox("Select Electric Duty", duty_options + ["Manual Entry"], index=0)
              electric_duty = st.number_input("Enter Electric Duty", min_value=0.0, step=0.01) if duty_selected == "Manual Entry" else duty_selected

              # Units Adjusted (for previous months)
              unit_adjusted = st.number_input("Units Adjusted (if any)", min_value=0.0, step=0.01, value=0.0)

              st.subheader("⚡ Surcharge Handling")
              surcharge_type_mapping = {
               1: "Additional PHL",
               2: "Uniform Quarterly",
               3: "Fuel Charge"
               }
              surcharge_types_df["TypeName"] = surcharge_types_df["SurchargeTypeID"].map(surcharge_type_mapping)
              # Step 1: Select Surcharge Type for the Current Billing Month
              surcharge_options = surcharge_types_df["TypeName"].unique().tolist() if not surcharge_types_df.empty else []
              total_monthly_surcharge =0.0
              selected_surcharge_types = st.multiselect("Select Surcharge Type for Current Billing Month", surcharge_options)
        
              selected_surcharge_data=[]
              for selected_surcharge_type in selected_surcharge_types:

                  if selected_surcharge_type !="Additional PHL":
             
                     st.markdown(f"**Surcharge Type: {selected_surcharge_type}**")
                     selected_surcharge_df= surcharge_types_df[surcharge_types_df["TypeName"]== selected_surcharge_type] if not surcharge_types_df.empty else []
                     surcharge_type_id = selected_surcharge_df["SurchargeTypeID"].iloc[0] if not selected_surcharge_df.empty else None
                     # Add an option for manual rate entry
                     # manual_entry = st.checkbox(f"Enter custom rate for {selected_surcharge_type}")
                       # if manual_entry:
                       #   custom_rate = st.number_input(f"Enter custom rate for {selected_surcharge_type}", min_value=-10.0, max_value=10.0, step=0.01)
                     #   effective_date = datetime.today().strftime("%m/%d/%Y")  # Today's Date

                     #  if st.button(f"Save Custom Rate for {selected_surcharge_type}"):
                      #     upsert_surcharge_rate(surcharge_type_id, custom_rate, effective_date)
                       #     conn.commit()

                       #    # Get the last inserted SurchargeID
                          #    surcharge_id = cursor.lastrowid
                         #   st.success(f"Custom rate saved with SurchargeID: {surcharge_id}")
                           #  selected_surcharge_data.append([
                            #    surcharge_id, selected_surcharge_type, custom_rate, effective_date
                             # ])

                   
                        #else:
                        #   surcharge_id = None  # Until user saves

                        #else:
                     if not selected_surcharge_df.empty:
              
                          selected_row = st.selectbox(f"Select Rate for {selected_surcharge_type}", selected_surcharge_df.apply(lambda row: f"Rate: {row['RatePerUnit']} | Effective: {row['EffectiveDate']}", axis=1).tolist())
                         # Extract selected row details
                          selected_index = selected_surcharge_df.apply(lambda row: f"Rate: {row['RatePerUnit']} | Effective: {row['EffectiveDate']}", axis=1).tolist().index(selected_row)
                          selected_surcharge_info = selected_surcharge_df.iloc[selected_index]
                          # Store data in 2D list
                          selected_surcharge_data.append([
                          selected_surcharge_info["SurchargeID"],  
                          selected_surcharge_info["SurchargeTypeID"],
                          selected_surcharge_type,
                          selected_surcharge_info["RatePerUnit"],
                          selected_surcharge_info["EffectiveDate"]
                           ])
                  else:
                     st.markdown(f"**Surcharge Type: {selected_surcharge_type}**")
                     selected_surcharge_df= surcharge_types_df[surcharge_types_df["TypeName"]== selected_surcharge_type] if not surcharge_types_df.empty else []
             
                     surcharge_type_id = selected_surcharge_df["SurchargeTypeID"].iloc[0] if not selected_surcharge_df.empty else None
                     # Add an option for manual rate entry
                     #manual_entry = st.checkbox(f"Enter custom rate for {selected_surcharge_type}")
                     #if manual_entry:
                           #   for units_from, units_to in [(1, 200), (201, 700)]:
                          #      custom_rate = st.number_input(
                         #      f"Enter Custom Rate for {selected_surcharge_type} (Units {units_from}-{units_to})",
                         #     min_value=-10.0, max_value=10.0, step=0.01
                             #     )
        
                            #  effective_date = datetime.today().strftime("%m/%d/%Y")  # Today's Date
        
                            #  if st.button(f"Save Custom Rate for {selected_surcharge_type} ({units_from}-{units_to})"):
                           #      upsert_surcharge_rate(surcharge_type_id, custom_rate, units_from, units_to, effective_date)

                         #       surcharge_id = cursor.lastrowid
                          #       st.success(f"Custom rate saved with SurchargeID: {surcharge_id}")

                         # Store selected surcharge info
                             #       data=fetch_surcharge_rate(cursor,surcharge_type_id,units_consumed,effective_date)
                           #
                           #       selected_surcharge_data.append([surcharge_id,selected_surcharge_type,selected_rate,effective_date])
            
                    

                          #else:
                     if not selected_surcharge_df.empty:
                         effective_date_options = selected_surcharge_df["EffectiveDate"].unique().tolist()
                         selected_effective_date = st.selectbox(f"Select Effective Date for {selected_surcharge_type}", effective_date_options)
                     
                         data=fetch_surcharge_rate(cursor,surcharge_type_id,units_consumed,selected_effective_date)
                         if data:
                             surcharge_id,selected_rate=data
                             if selected_rate is None:
                                 st.warning(f"No rate found for SurchargeTypeID: {surcharge_type_id}, Units: {units_consumed}, Effective Date: {selected_effective_date}.")
                             selected_surcharge_data.append([surcharge_id,surcharge_type_id,selected_surcharge_type,selected_rate,selected_effective_date])
        
              if selected_surcharge_data:
                 total_monthly_surcharge = sum(float(row[3]) * units_consumed for row in selected_surcharge_data)
                 for data in selected_surcharge_data:
                     surcharge_id = data[0]
                     surcharge_amount = data[3]*units_consumed
    
                     insert_or_update_readingsurchargemapping(
                     reading_id=reading_id,
                     surcharge_id=surcharge_id,
                     billing_month=billing_month,
                     adjusted_billing_month=billing_month,
                     surcharge_amount=surcharge_amount,
                     )


              # Step 2: Select Adjusted Months for Surcharge Adjustments
              previous_months = get_previous_billing_months(cursor,flat_no, billing_month)
              adjusted_months = st.multiselect("Select Adjusted Billing Months", previous_months)
              selected_adjusted_surcharge_data=[]
               # Step 3: Select Surcharge Type for Each Adjusted Month
              total_adjusted_surcharge = 0.0
              selected_adjusted_surcharge_data=[]
              for adjusted_month in adjusted_months:
                 units_adjusted=get_units_adjusted(cursor,flat_no,adjusted_month)
                 st.markdown(f"**Adjusted Billing Month: {adjusted_month}**")
                 selected_adjusted_surcharge_types = st.multiselect(f"Select Surcharge Type for :{adjusted_month}", surcharge_options)
                 for selected_adjusted_surcharge_type in selected_adjusted_surcharge_types:

                     if selected_adjusted_surcharge_type !="Additional PHL":
             
                         st.markdown(f"**Surcharge Type: {selected_adjusted_surcharge_type}**")
                         selected_surcharge_df= surcharge_types_df[surcharge_types_df["TypeName"]== selected_adjusted_surcharge_type] if not surcharge_types_df.empty else []
                         surcharge_type_id = selected_surcharge_df["SurchargeTypeID"].iloc[0] if not selected_surcharge_df.empty else None
                          # Add an option for manual rate entry
                          #manual_entry = st.checkbox(f"Enter custom rate for {selected_adjusted_surcharge_type}")
                          #if manual_entry:
                           #   custom_rate = st.number_input(f"Enter custom rate for {selected_adjusted_surcharge_type}", min_value=-10.0, max_value=10.0, step=0.01)
                           #   effective_date = datetime.today().strftime("%m/%d/%Y")  # Today's Date

                         #  if st.button(f"Save Custom Rate for {selected_adjusted_surcharge_type}"):
                         #      upsert_surcharge_rate(surcharge_type_id, custom_rate, effective_date)
                         #      conn.commit()

                         #      # Get the last inserted SurchargeID
                         #      surcharge_id = cursor.lastrowid
                         #      st.success(f"Custom rate saved with SurchargeID: {surcharge_id}")
                            #      selected_adjusted_surcharge_data.append([
                             #       surcharge_id, selected_adjusted_surcharge_type, custom_rate, units_adjusted,effective_date
                            #       ])
                          #   else:
                           #       surcharge_id = None  # Until user saves

                            #else:
                         if not selected_surcharge_df.empty:
              
                              selected_row = st.selectbox(f"Select Rate for {selected_adjusted_surcharge_type}", selected_surcharge_df.apply(lambda row: f"Rate: {row['RatePerUnit']} | Effective: {row['EffectiveDate']}", axis=1).tolist())
                             # Extract selected row details
                              selected_index = selected_surcharge_df.apply(lambda row: f"Rate: {row['RatePerUnit']} | Effective: {row['EffectiveDate']}", axis=1).tolist().index(selected_row)
                              selected_surcharge_info = selected_surcharge_df.iloc[selected_index]
                               # Store data in 2D list
                              selected_adjusted_surcharge_data.append([
                              selected_surcharge_info["SurchargeID"],     
                              selected_surcharge_info["SurchargeTypeID"],
                              selected_adjusted_surcharge_type,
                              selected_surcharge_info["RatePerUnit"],
                              units_adjusted,
                              adjusted_month,
                              selected_surcharge_info["EffectiveDate"]
                              ])
                     else:
                          st.markdown(f"**Surcharge Type: {selected_adjusted_surcharge_type}**")
                          selected_surcharge_df= surcharge_types_df[surcharge_types_df["TypeName"]== selected_adjusted_surcharge_type] if not surcharge_types_df.empty else []
                          surcharge_type_id = selected_surcharge_df["SurchargeTypeID"].iloc[0] if not selected_surcharge_df.empty else None
                              # Add an option for manual rate entry
                              #manual_entry = st.checkbox(f"Enter custom rate for {selected_adjusted_surcharge_type}")
                                #if manual_entry:
                               #  for units_from, units_to in [(1, 200), (201, 700)]:
                             #     custom_rate = st.number_input(
                              #    f"Enter Custom Rate for {selected_adjusted_surcharge_type} (Units {units_from}-{units_to})",
                             #   min_value=-10.0, max_value=10.0, step=0.01
                              #  )
        
                             #    effective_date = datetime.today().strftime("%m/%d/%Y")  # Today's Date
        
                               #   if st.button(f"Save Custom Rate for {selected_surcharge_type} ({units_from}-{units_to})"):
                             #       upsert_surcharge_rate(surcharge_type_id, custom_rate, units_from, units_to, effective_date)

                               #       surcharge_id = cursor.lastrowid
                                  #       st.success(f"Custom rate saved with SurchargeID: {surcharge_id}")

                                  #   # Store selected surcharge info
                               #selected_rate,surcharge_id=fetch_surcharge_rate(surcharge_type_id,units_adjusted,effective_date)

                               #selected_adjusted_surcharge_data.append([surcharge_id,surcharge_type_id,selected_adjusted_surcharge_type,selected_rate,units_adjusted,adjusted_month,effective_date])
            
                    

                                   #else:
                          if not selected_surcharge_df.empty:
                                effective_date_options = selected_surcharge_df["EffectiveDate"].unique().tolist()
                                selected_effective_date = st.selectbox(f"Select Effective Date for {selected_adjusted_surcharge_type}", effective_date_options)
                     
                                data=fetch_surcharge_rate(cursor,surcharge_type_id,units_consumed,selected_effective_date)
                                if data:
                                      surcharge_id,selected_rate=data
                                      selected_adjusted_surcharge_data.append([surcharge_id,surcharge_type_id,selected_adjusted_surcharge_type,selected_rate,units_adjusted,adjusted_month,selected_effective_date])
        
        
              total_adjusted_surcharge = sum(float(row[3] if row[3] else 0) * float(row[4] if row[4] else 0) for row in selected_adjusted_surcharge_data)
              for data in selected_adjusted_surcharge_data:
                  surcharge_id = data[0]
                  surcharge_amount = data[3]*data[4]
                  adjusted_billing_month=data[5]
    
                  insert_or_update_readingsurchargemapping(
                  reading_id=reading_id,
                  surcharge_id=surcharge_id,
                  billing_month=billing_month,
                  adjusted_billing_month=adjusted_billing_month,
                  surcharge_amount=surcharge_amount,
                  )


        

              # Display Computed Values
              st.text(f"🔹 **Current Month Surcharge:** {total_monthly_surcharge:.2f} PKR")
              st.text(f"🔹 **Adjusted Surcharge Total:** {total_adjusted_surcharge:.2f} PKR")
             # Insert Record Button
              if st.button("📌 Insert Record"):
                insert_bill(person_id,st.session_state.fetched_reading_id, flat_no,user_category,name,billing_month,previous_reading,present_reading,units_consumed, electric_duty, gst_value, unit_adjusted,total_monthly_surcharge,total_adjusted_surcharge)
            

                # Close the connection
        conn.close()
 
    elif selected_option == "Update/Delete Bill Record":
     st.title("✏️ Update or 🗑️ Delete Bill Record")

     conn = get_connection()
     cursor = conn.cursor()

    
     gst_rates_df = get_table_data("GSTRates")
     duty_rates_df = get_table_data("ElectricDutyRates")
     surcharge_types_df = get_surcharge_rates()
     # Fetch available Flats
     cursor.execute("SELECT DISTINCT FlatNo FROM BillingReadings")
     flat_list = [row[0] for row in cursor.fetchall()]
     if not flat_list:
        st.warning("⚠️ No flats found with billing records!")
        conn.close()
        st.stop()

     flat_no = st.selectbox("Select Flat No", flat_list)

     # Fetch available Billing Months for the selected flat
     cursor.execute("SELECT DISTINCT BillingMonth FROM BillingReadings WHERE FlatNo=?", (flat_no,))
     month_list = [row[0] for row in cursor.fetchall()]
     if not month_list:
        st.warning("⚠️ No billing records found for this flat!")
        conn.close()
        st.stop()

     month = st.selectbox("Select Billing Month", month_list)
    

     # Fetch Users associated with the flat
     cursor.execute("SELECT PersonID, Name FROM Users WHERE FlatNo=?", (flat_no,))
     users = cursor.fetchall()
    
     if users:
        user_dict = {f"{row[1]} (ID: {row[0]})": row for row in users}
        selected_user = st.selectbox("Select Person", list(user_dict.keys()))
        person_id, person_name = user_dict[selected_user]
     else:
        st.warning("⚠️ No user found for this flat!")
        person_id, person_name = None, "Unknown"

     st.text(f"👤 Person ID: {person_id}")
     st.text(f"📛 Name: {person_name}")

     # Fetch Billing Data
     bill_data = fetch_complete_bill(flat_no, month)

     if bill_data:
        (
            reading_id, previous_reading, present_reading,_,unit_adjusted, 
            _, _, _, electric_duty, gst, 
            _,_
        ) = bill_data

        present_reading = st.number_input("New Present Reading (kWh)", min_value=0.0, step=0.01, value=present_reading)
        units_consumed = calculate_units_consumed(previous_reading, present_reading)

        gst = st.selectbox("Select GST (%)", gst_rates_df["GST"].tolist(), index=0) if not gst_rates_df.empty else 0.0
       
        electric_duty = st.selectbox("Select Electric Duty", duty_rates_df["ElectricDuty"].tolist(), index=0) if not duty_rates_df.empty else 0.0
        
        unit_adjusted = st.number_input("Units Adjusted (if any)", min_value=0.0, step=0.01, value=unit_adjusted)

        surcharge_data = fetch_surcharge_mapping(cursor,reading_id, month)
        
        total_monthly_surcharge = 0
        total_adjusted_surcharge = 0
        if surcharge_data:
          st.subheader("⚡ Surcharge Handling")

          surcharge_type_mapping = {
          1: "Additional PHL",
          2: "Uniform Quarterly",
          3: "Fuel Charge"
          }

          surcharge_types_df["TypeName"] = surcharge_types_df["SurchargeTypeID"].map(surcharge_type_mapping)
          surcharge_options = surcharge_types_df["TypeName"].unique().tolist() if not surcharge_types_df.empty else []
          updated_current_surcharge_data = []
          updated_adjusted_surcharge_data = []
         

          for record in surcharge_data:
             (surcharge_id, surcharge_type_id, surcharge_type, old_rate, adjusted_billing_month, surcharge_amount, adjustment_reason,old_effective_date) = record

             # Ensure the DataFrame is not empty before filtering
             if not surcharge_types_df.empty:
                 selected_surcharge_df = surcharge_types_df[surcharge_types_df["TypeName"] == surcharge_type]
    

                 if adjusted_billing_month == month:
                     if surcharge_type == "Additional PHL":
                         st.markdown(f"**Surcharge Type: {surcharge_type}**")

                         # Fetch effective date options only if data exists
                         effective_date_options = selected_surcharge_df["EffectiveDate"].unique().tolist() if not selected_surcharge_df.empty else []

                         selected_effective_date = st.selectbox(f"Select Effective Date for {surcharge_type}", effective_date_options)
                         
                         data = fetch_surcharge_rate(cursor,surcharge_type_id, units_consumed, selected_effective_date)

                         if data:
                             surcharge_id, selected_rate = data
                             updated_current_surcharge_data.append([surcharge_id, surcharge_type_id, surcharge_type, selected_rate,selected_effective_date])
                     else: 
                         st.markdown(f"**Surcharge Type: {surcharge_type}**")  

                
                         # Create a list of display strings for selection
                         surcharge_display_options = selected_surcharge_df.apply(
                         lambda row: f"Rate: {row['RatePerUnit']} | Effective: {row['EffectiveDate']}", axis=1
                         ).tolist()

                         # Dropdown for user to select surcharge rate entry
                         selected_display_value = st.selectbox(f"Select Rate for {surcharge_type}", surcharge_display_options)

                         # Extract numeric rate and effective date from the selected string
                         selected_index = surcharge_display_options.index(selected_display_value)
                         selected_surcharge_info = selected_surcharge_df.iloc[selected_index]

                         # Allow manual rate input, pre-filled with old rate
                         selected_rate = st.number_input("Enter Rate", value=float(selected_surcharge_info["RatePerUnit"]))

                         # Store data in a 2D list
                         updated_current_surcharge_data.append([
                         selected_surcharge_info["SurchargeID"],     
                         selected_surcharge_info["SurchargeTypeID"],
                         surcharge_type,
                         selected_rate,  # Updated rate from user input
                         selected_surcharge_info["EffectiveDate"]
                         ])
                 else:
                     units_adjusted=get_units_adjusted(cursor,flat_no,adjusted_billing_month)
                     if surcharge_type == "Additional PHL":
                         st.markdown(f"**Surcharge Type: {surcharge_type}**")

                         # Fetch effective date options only if data exists
                         effective_date_options = selected_surcharge_df["EffectiveDate"].unique().tolist() if not selected_surcharge_df.empty else []

                         effective_date = st.selectbox(f"Select Effective Date for {surcharge_type}", effective_date_options)
                         selected_effective_date = st.date_input("Enter Effective Date",  value=old_effective_date)
                         data = fetch_surcharge_rate(surcharge_type_id, units_consumed, selected_effective_date)

                         if data:
                             surcharge_id, selected_rate = data
                             updated_adjusted_surcharge_data.append([surcharge_id, surcharge_type_id, surcharge_type, selected_rate,units_adjusted,adjusted_billing_month,selected_effective_date])
                     else: 
                         st.markdown(f"**Surcharge Type: {surcharge_type}**")  

                
                         # Create a list of display strings for selection
                         surcharge_display_options = selected_surcharge_df.apply(
                         lambda row: f"Rate: {row['RatePerUnit']} | Effective: {row['EffectiveDate']}", axis=1
                         ).tolist()

                         # Dropdown for user to select surcharge rate entry
                         selected_display_value = st.selectbox(f"Select Rate for {surcharge_type}", surcharge_display_options)

                         # Extract numeric rate and effective date from the selected string
                         selected_index = surcharge_display_options.index(selected_display_value)
                         selected_surcharge_info = selected_surcharge_df.iloc[selected_index]

                         # Allow manual rate input, pre-filled with old rate
                         selected_rate = st.number_input("Enter Rate", value=float(selected_surcharge_info["RatePerUnit"]))

                         # Store data in a 2D list
                         updated_adjusted_surcharge_data.append([
                         selected_surcharge_info["SurchargeID"],     
                         selected_surcharge_info["SurchargeTypeID"],
                         surcharge_type,
                         selected_rate,
                         units_adjusted,
                         adjusted_billing_month,  # Updated rate from user input
                         selected_surcharge_info["EffectiveDate"]
                         ]) 
                      
          if updated_current_surcharge_data:
             total_monthly_surcharge = sum(float(row[3]) * units_consumed for row in updated_current_surcharge_data)
             for data in updated_current_surcharge_data:
                 surcharge_id = data[0]
                 surcharge_amount = data[3]*units_consumed
    
                 insert_or_update_readingsurchargemapping(
                 reading_id=reading_id,
                 surcharge_id=surcharge_id,
                 billing_month=month,
                 adjusted_billing_month=month,
                 surcharge_amount=surcharge_amount,
                 )
              
          if updated_adjusted_surcharge_data:
           total_adjusted_surcharge = sum(float(row[3] if row[3] else 0) * float(row[4] if row[4] else 0) for row in updated_adjusted_surcharge_data)
           for data in updated_adjusted_surcharge_data:
              surcharge_id = data[0]
              surcharge_amount = data[3]*data[4]
              adjusted_billing_month=data[5]
    
              insert_or_update_readingsurchargemapping(
               reading_id=reading_id,
               surcharge_id=surcharge_id,
               billing_month=month,
               adjusted_billing_month=adjusted_billing_month,
               surcharge_amount=surcharge_amount,
               )
              


        

         # Display Computed Values
        st.text(f"🔹 **Current Month Surcharge:** {total_monthly_surcharge:.2f} PKR")
        st.text(f"🔹 **Adjusted Surcharge Total:** {total_adjusted_surcharge:.2f} PKR")
            
        if st.button("✏️ Update Bill Record"):
            update_bill(flat_no, month, present_reading, electric_duty, gst,unit_adjusted,total_monthly_surcharge,total_adjusted_surcharge)
           
        if "delete_confirm" not in st.session_state:
             st.session_state.delete_confirm = False   
        if st.button("🗑️ Delete Bill Record"):
             st.session_state.delete_confirm = True  # Set confirmation state to True

        if st.session_state.delete_confirm:
              st.warning("⚠️ Are you sure you want to delete this bill? This action cannot be undone.")
              col1, col2 = st.columns(2)

              with col1:
                 if st.button("✅ Confirm Delete"):
                     delete_bill(flat_no, month)
                     st.session_state.delete_confirm = False  # Reset confirmation after deletion
    
              with col2:
                  if st.button("❌ Cancel"):
                     st.session_state.delete_confirm = False  # Reset confirmation
                     st.success("Deletion Cancelled.")
            

     conn.close()


    elif selected_option == "Generate Bill":
        st.title("⚡ User-Specific Electricity Bill Generation")
        
        # Option 1: Generate Bill for a specific user and month
        flat_no = st.text_input("Enter Flat Number:", key="flat_no_input")
        person_id = st.text_input("Enter Person ID:", key="person_id_input")
        billing_month = st.text_input("Enter Billing Month (YYYY-MM):", key="single_bill_month")

        if st.button("Fetch Bill Details"):
            if flat_no and billing_month:
                # Fetch bill details (Note: No PersonID is used here)
                bill = fetch_complete_bill(flat_no, billing_month)  
                
                if bill:
                    # Unpack bill details
                    bill_id, prev_reading, pres_reading, units_consumed, units_adjusted, rate_per_unit, var_charges, elec_duty, gst, surcharge, net_amount, payable_amount = bill

                    # Store bill details in session state
                    st.session_state.bill_id = bill_id
                    st.session_state.prev_reading = prev_reading
                    st.session_state.pres_reading = pres_reading
                    st.session_state.units_consumed = units_consumed
                    st.session_state.units_adjusted = units_adjusted
                    st.session_state.rate_per_unit = rate_per_unit
                    st.session_state.var_charges = var_charges
                    st.session_state.elec_duty = elec_duty
                    st.session_state.gst = gst
                    st.session_state.surcharge = surcharge
                    st.session_state.net_amount = net_amount
                    st.session_state.payable_amount = payable_amount

                    # Fetch user details for PDF generation (Only if person_id is given)
                    if person_id:
                        conn = sqlite3.connect("billing_system.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT Name FROM Users WHERE FlatNo = ? AND PersonID = ?", (flat_no, person_id))
                        result = cursor.fetchone()
                        conn.close()
                        
                        if result:
                            st.session_state.name = result[0]
                        else:
                            st.warning("User not found for the given Flat Number and Person ID.")
                
                else:
                    st.error("No bill found for the given Flat Number and Billing Month.")
            else:
                st.error("Please enter Flat Number and Billing Month.")  # Removed Person ID from this error

        # If bill details are fetched, display editable fields
        if "bill_id" in st.session_state:
            # Editable fields with current values
            present_reading = st.number_input("Present Reading:", value=st.session_state.pres_reading)
            units_adjusted = st.number_input("Units Adjusted:", value=st.session_state.units_adjusted)
            electric_duty = st.number_input("Electric Duty:", value=st.session_state.elec_duty)
            gst = st.number_input("GST:", value=st.session_state.gst)
            surcharge = st.number_input("Surcharge:", value=st.session_state.surcharge)

            if st.button("Update Bill"):
                # Call update_bill function with modified values
                update_bill(
                    flat_no=flat_no,
                    month=billing_month,
                    present_reading=present_reading if present_reading != st.session_state.pres_reading else None,
                    electric_duty=electric_duty if electric_duty != st.session_state.elec_duty else None,
                    gst=gst if gst != st.session_state.gst else None,
                    units_adjusted=units_adjusted if units_adjusted != st.session_state.units_adjusted else None,
                    surcharge=surcharge if surcharge != st.session_state.surcharge else None
                )
                # Fetch updated bill details
                updated_bill = fetch_complete_bill(flat_no, billing_month)
                if updated_bill:
                    # Unpack and store updated details
                    (reading_id, prev_reading, pres_reading, units_consumed, units_adjusted, bill_id, 
                    rate_per_unit, var_charges, elec_duty, gst, surcharge, net_amount, payable_amount) = updated_bill

                    st.session_state.updated_bill = {
                        "units_consumed": units_consumed,
                        "variable_charges": var_charges,
                        "net_amount": net_amount,
                        "payable_amount": payable_amount
                    }
                    st.session_state.pres_reading = pres_reading
                    st.session_state.units_adjusted = units_adjusted
                    st.session_state.elec_duty = elec_duty
                    st.session_state.gst = gst
                    st.session_state.surcharge = surcharge

            # If bill is updated, show download button
            if "updated_bill" in st.session_state:
                # Generate updated PDF
                pdf_path = generate_pdf(
                    flat_no, st.session_state.person_id, st.session_state.name, billing_month,
                    f"01-{billing_month.split('-')[1]}-25", st.session_state.prev_reading, st.session_state.pres_reading,
                    st.session_state.updated_bill["units_consumed"], st.session_state.elec_duty, st.session_state.gst, st.session_state.surcharge,
                    st.session_state.updated_bill["variable_charges"], st.session_state.updated_bill["net_amount"],
                    st.session_state.updated_bill["payable_amount"]
                )

                # Provide download button for the updated PDF
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📥 Download Updated Bill PDF",
                        f,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )

        # Separator
        st.markdown("---")  

        # Option 2: Bulk Electricity Bill Generation
        st.title("📑 Batch Electricity Bill Generation")
        selected_month = st.text_input("Enter Billing Month (YYYY-MM):", key="bulk_bill_month")  # Unique key added

        if st.button("Generate Bills"):
            if selected_month:
                billing_data = fetch_billing_data(selected_month)
                if billing_data:
                    pdf_file = Generate_bulk_bill_pdf(billing_data, selected_month)
                    st.download_button(
                        label="Download PDF",
                        data=pdf_file.getvalue(),  # Ensure binary data is passed
                        file_name=f"Bulk_Bills_{selected_month}.pdf",
                        mime="application/pdf"
                    )

                else:
                    st.warning("No billing data found for the selected month!")
            else:
                st.error("Please enter a valid month in YYYY-MM format.")

    elif selected_option == "Billing Records":
        st.title("📊 View Records")

        # List of available tables
        tables = [
            "BillingReadings", "BillingCharges", "ConsumptionHistory",
            "TariffSlabs", "GSTRates", "ElectricDutyRates",
        ]
        
        # Dropdown to select a table
        selected_table = st.selectbox("Select a Table", tables)
        
        # Fetch data for the selected table
        df = get_table_data(selected_table)
        
        # Display the raw dataframe
        st.write(f"### {selected_table} Table")
        st.dataframe(df)

        # Add advanced search filters
        st.markdown("---")
        st.write("### 🔍 Advanced Search")
        
        # Use columns for better alignment
        col1, col2 = st.columns(2)
        
        # Initialize filtered DataFrame
        filtered_df = df.copy()

        # Dynamic search filters based on the selected table
        if selected_table == "BillingReadings":
            with col1:
                flat_no_filter = st.text_input("Search by Flat No (exact match):")
            with col2:
                billing_month_filter = st.text_input("Search by Billing Month (YYYY-MM):")
            
            # Apply filters
            if flat_no_filter:
                filtered_df = filtered_df[filtered_df["FlatNo"].astype(str) == flat_no_filter]
            if billing_month_filter:
                filtered_df = filtered_df[filtered_df["BillingMonth"].astype(str) == billing_month_filter]
        
        elif selected_table == "BillingCharges":
            with col1:
                flat_no_filter = st.text_input("Search by Flat No (exact match):")

            # Apply filters
            if flat_no_filter:
                filtered_df = filtered_df[filtered_df["FlatNo"].astype(str) == flat_no_filter]

        elif selected_table == "ConsumptionHistory":
            with col1:
                billing_month_filter = st.text_input("Search by Billing Month (YYYY-MM):")

            # Apply filters
            if billing_month_filter:
                filtered_df = filtered_df[filtered_df["BillingMonth"].astype(str) == billing_month_filter]

        # General Search if no specific filters are applied
        if not any([flat_no_filter, billing_month_filter]):
            st.markdown("---")
            st.write("### 🔍 General Search")
            search_term = st.text_input("Search within the table (all columns):")
            if search_term:
                filtered_df = filtered_df[filtered_df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
        
        # Display filtered results
        if not filtered_df.empty:
            st.write(f"### Filtered Results ({len(filtered_df)} records found)")
            st.dataframe(filtered_df)
        else:
            st.warning("No records found matching your search criteria.")

# Rate Management Logic
elif selected_section == "⚡ Rate Management":
    st.title("⚡ Manage Rates")
    effective_date = datetime.today().strftime('%Y-%m-%d')

    # Handle the selected option from the sidebar
    if selected_option == "Insert/Update Rates":
        st.subheader("Insert/Update Rates")

        # GST Rate
        st.markdown("### GST Rate")
        gst_rate = st.number_input("Enter GST Rate (%)", min_value=0.0, step=0.1, key="gst_rate")
        if st.button("💾 Save GST Rate"):
            upsert_gst_rate(gst_rate, effective_date)
            st.success("GST Rate updated!")

        # Electric Duty Rate
        st.markdown("### Electric Duty Rate")
        duty_rate = st.number_input("Enter Electric Duty Rate (%)", min_value=0.0, step=0.1, key="duty_rate")
        if st.button("💾 Save Electric Duty Rate"):
            upsert_electric_duty_rate(duty_rate, effective_date)
            st.success("Electric Duty Rate updated!")

        # Surcharge Rate
        st.markdown("### Surcharge Rate")
        surcharge_type_id = st.number_input("Surcharge Type ID", min_value=1, step=1, key="surcharge_type_id")
        rate_per_unit = st.number_input("Rate Per Unit", min_value=0.0, step=0.1, key="rate_per_unit")
        units_from = st.number_input("Units From", min_value=0, step=1, key="units_from")
        units_to = st.number_input("Units To", min_value=0, step=1, key="units_to")
        if st.button("💾 Save Surcharge Rate"):
            upsert_surcharge_rate(surcharge_type_id, rate_per_unit, units_from, units_to, effective_date)
            st.success("Surcharge Rate updated!")

    elif selected_option == "View Rates":
        st.subheader("View Rates")

        # GST Rates
        st.markdown("### GST Rates")
        gst_rates_df = get_gst_rates()
        st.dataframe(gst_rates_df)

        # Electric Duty Rates
        st.markdown("### Electric Duty Rates")
        duty_rates_df = get_electric_duty_rates()
        st.dataframe(duty_rates_df)

        # Surcharge Rates
        st.markdown("### Surcharge Rates")
        surcharge_rates_df = get_surcharge_rates()
        st.dataframe(surcharge_rates_df)