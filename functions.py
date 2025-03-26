import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from io import BytesIO
import streamlit as st
import os

# Database connection 
def get_connection():
    return sqlite3.connect("billing_system.db", check_same_thread=False)

# Fetch table data 
def get_table_data(table_name):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

# Insert user data 
def insert_user(person_id, name, flat_no, user_type, load_sanctioned, phase):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Users (PersonID, Name, FlatNo, UserType, LoadSanctioned, Phase)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (person_id, name, flat_no, user_type, load_sanctioned, phase))
    conn.commit()
    conn.close()

# Update user data 
def update_user(person_id, name, flat_no, user_type, load_sanctioned, phase):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Users SET Name=?, FlatNo=?, UserType=?, LoadSanctioned=?, Phase=?
        WHERE PersonID=?
    """, (name, flat_no, user_type, load_sanctioned, phase, person_id))
    conn.commit()
    conn.close()

# Delete user data 
def delete_user(person_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Users WHERE PersonID=?", (person_id,))
    conn.commit()
    conn.close()

def generate_pdf(flat_no, person_id, name,billing_month, reading_date, 
                 previous_reading, present_reading, units_consumed, electric_duty, 
                 gst, surcharge, variable_charges, net_amount, payable_amount):

    file_path = f"{flat_no}_ElectricBill_{billing_month}.pdf"
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 50, "NED UNIVERSITY OF ENGINEERING & TECHNOLOGY")
    c.drawCentredString(width / 2, height - 70, "DIRECTORATE OF WORKS & SERVICES")
    c.drawCentredString(width / 2, height - 90, "ELECTRIC BILL FOR NED STAFF COLONY")

    # User Details
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 120, f"Flat No: {flat_no}")
    c.drawString(250, height - 120, f"Load Sanctioned: 1 kW")
    c.drawString(50, height - 140, f"Pers No: {person_id}")
    c.drawString(250, height - 140, f"Phase: 1")
    c.drawString(50, height - 160, f"Name: {name}")
    c.drawString(50, height - 200, f"Billing Month: {billing_month}")
    c.drawString(250, height - 200, f"Reading Date: {reading_date}")

    # Table Headers
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.blue)
    c.drawString(50, height - 230, "Billing Detail Residential Tariff (October 2024 - Onwards)")

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.black)
    c.drawString(50, height - 250, "Units Details")
    c.drawString(50, height - 270, f"Previous Reading: {previous_reading}")
    c.drawString(50, height - 290, f"Present Reading: {present_reading}")
    c.drawString(50, height - 310, f"Units Consumed: {units_consumed}")
    c.drawString(50, height - 330, "Units Adjusted: 0")
    c.drawString(50, height - 350, f"Billing Units: {units_consumed}")

    # Charges Section
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 380, "Charges Details (PKR)")
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 400, f"Variable Charges: {variable_charges}")
    c.drawString(50, height - 420, f"Electric Duty: {electric_duty}")
    c.drawString(50, height - 460, f"GST: {gst}")
    c.drawString(50, height - 480, f"Surcharge: {surcharge}")
    c.drawString(50, height - 500, f"Net Amount: {net_amount}")
    c.drawString(50, height - 520, f"Payable Amount: {payable_amount}")

    # Footer
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, height - 550, "Note: Meter Reading will be taken on 1st of every month.")
    c.drawString(50, height - 570, "This is a computer-generated bill and does not require a signature.")
    c.drawString(400, height - 590, f"Bill Generated on: {datetime.now().strftime('%d/%m/%Y')}")

    c.save()
    return file_path    
# Get the previous month from the current billing month    
def get_previous_month(billing_month):
    year, month = map(int, billing_month.split('-'))
    previous_month = (datetime(year, month, 1) - timedelta(days=1)).strftime('%Y-%m')
    return previous_month


def calculate_units_consumed(previous_reading, present_reading):
    #"""Calculate units consumed, ensuring it's non-negative."""
    return max(0, abs(present_reading - previous_reading))



def get_previous_billing_months(cursor, flat_no, billing_month):
    cursor.execute("""
        SELECT DISTINCT BillingMonth 
        FROM BillingReadings 
        WHERE FlatNo = ? 
        ORDER BY BillingMonth DESC
    """, (flat_no,))
    return [row[0] for row in cursor.fetchall()]

def get_surcharge_types(cursor):
    cursor.execute("SELECT SurchargeTypeID, TypeName FROM SurchargeType")
    return {row[0]: row[1] for row in cursor.fetchall()}

def get_units_adjusted(cursor, flat_no, month):

    query = """
        SELECT UnitsConsumed FROM BillingCharges bc
        JOIN BillingReadings br ON bc.ReadingID = br.ReadingID
        WHERE br.FlatNo = ? AND br.BillingMonth = ?
    """
    cursor.execute(query, (flat_no, month))
    result = cursor.fetchone()[0]
    return result if result else 0


def fetch_rate_per_unit(cursor, units_consumed, user_category):
    print(f"🔍 Fetching rate for UserCategory: {user_category}, Units Consumed: {units_consumed}")

    # Step 1: Check if data exists for the given category
    cursor.execute("SELECT COUNT(*) FROM TariffSlabs WHERE UserCategory = ?", (user_category,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(f"❌ No records found for UserCategory: {user_category}")
        return 0.0  # Return 0 if no matching category exists

    # Step 2: Fetch applicable RatePerUnit with explicit CAST
    query = """
        SELECT RatePerUnit 
        FROM TariffSlabs
        WHERE UserCategory = ?  
        AND CAST(MinUnits AS REAL) <= CAST(? AS REAL) 
        AND (MaxUnits IS NULL OR CAST(MaxUnits AS REAL) >= CAST(? AS REAL))
        ORDER BY RateEffectiveDate DESC 
        LIMIT 1
    """
    
    cursor.execute(query, (user_category, units_consumed, units_consumed))
    result = cursor.fetchone()

    if result:
        print(f"✅ Query Result: {result[0]}")
        return float(result[0])  # Ensure correct return type
    else:
        print(f"⚠️ No matching rate found for {units_consumed} units in category {user_category}")
        return 0.0  # Return default value if no match



def get_surcharge_amount(cursor, flat_no, month, surcharge_types):
    if not surcharge_types:
        return 0
    placeholders = ",".join(["?"] * len(surcharge_types))
    query = f"""
        SELECT SUM(rsm.SurchargeAmount) 
        FROM ReadingSurchargeMapping rsm
        JOIN BillingReadings br ON rsm.ReadingID = br.ReadingID
        WHERE br.FlatNo = ? AND rsm.BillingMonth = ? AND rsm.SurchargeID IN ({placeholders})
    """
    cursor.execute(query, (flat_no, month, *surcharge_types))
    result = cursor.fetchone()[0]
    return result if result else 0

def fetch_gst_electric_duty_ids(cursor, gst_rate, electric_duty):
    query = """
        SELECT GSTID FROM GSTRates WHERE GST = ?
    """
    cursor.execute(query, (gst_rate,))
    gst_id = cursor.fetchone()
    gst_id = gst_id[0] if gst_id else None  # Extract value if found

    query = """
        SELECT DutyID FROM ElectricDutyRates  WHERE ElectricDuty = ?
    """
    cursor.execute(query, (electric_duty,))
    electric_duty_id = cursor.fetchone()
    electric_duty_id = electric_duty_id[0] if electric_duty_id else None  # Extract value if found

    return gst_id, electric_duty_id

def get_date(billing_month: str) -> str:
    """
    Returns the 1st day of the next month after the given billing month.

    Args:
        billing_month (str): A string in "YYYY-MM" format (e.g., "2024-03").

    Returns:
        str: The date as "YYYY-MM-DD" format (e.g., "2024-04-01").
    """
    try:
        # Convert "YYYY-MM" to a datetime object
        month_dt = datetime.strptime(billing_month, "%Y-%m")

        # Move to the first day of the next month
        next_month_dt = (month_dt.replace(day=28) + timedelta(days=4)).replace(day=1)

        return next_month_dt.strftime("%Y-%m-%d")

    except ValueError:
        return "Invalid billing month format!"

def insert_or_update_readingsurchargemapping(reading_id, surcharge_id, billing_month, adjusted_billing_month, surcharge_amount, adjustment_reason=None):
    """
    Inserts or updates data in the ReadingSurchargeMapping table.

    If a record with the same (ReadingID, SurchargeID, BillingMonth, AdjustedBillingMonth) exists,
    it updates the SurchargeAmount and AdjustmentReason. Otherwise, it inserts a new record.

    Parameters:
        reading_id (int): Foreign key referencing BillingReadings.
        surcharge_id (int): Foreign key referencing Surcharge.
        billing_month (str): The current billing month (YYYY-MM-DD format).
        adjusted_billing_month (str): The previous billing month being adjusted (YYYY-MM-DD format).
        surcharge_amount (float): The surcharge amount (must be >= 0).
        adjustment_reason (str, optional): Reason for adjustment (default is None).

    Returns:
        str: Success or error message.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO ReadingSurchargeMapping (
                ReadingID, SurchargeID, BillingMonth, AdjustedBillingMonth, SurchargeAmount, AdjustmentReason
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ReadingID, SurchargeID, BillingMonth, AdjustedBillingMonth) 
            DO UPDATE SET 
                SurchargeAmount = EXCLUDED.SurchargeAmount,
                AdjustmentReason = COALESCE(EXCLUDED.AdjustmentReason, ReadingSurchargeMapping.AdjustmentReason);
        """, (reading_id, surcharge_id, billing_month, adjusted_billing_month, surcharge_amount, adjustment_reason))

        conn.commit()
        return "✅ Insert/Update successful!"
    
    except Exception as e:
        conn.rollback()
        return f"❌ Error: {e}"
    
    finally:
        cursor.close()
        conn.close()

# Insert a new bill record
import sqlite3
import os
import streamlit as st

def insert_reading(cursor, conn, flat_no, previous_reading, present_reading):
    cursor.execute("""
        INSERT INTO BillingReadings (FlatNo, PreviousReading, PresentReading)
        VALUES (?, ?, ?)
    """, (flat_no, previous_reading, present_reading))
    conn.commit()
    cursor.execute("SELECT last_insert_rowid()")
    return cursor.fetchone()[0]  # Return the correct reading ID

def insert_bill(person_id, reading_id, flat_no, user_category, name, month, previous_reading, present_reading, 
                units_consumed, electric_duty, gst_rate, unit_adjusted, total_monthly_surcharge, total_adjusted_surcharge):
    try:
        conn = sqlite3.connect("billing_system.db")
        cursor = conn.cursor()

        # Fetch rate per unit
        rate_per_unit = fetch_rate_per_unit(cursor, units_consumed, user_category)
        reading_date = get_date(month)

        # Calculate Variable Charges
        variable_charges = units_consumed * rate_per_unit
        reading_id=reading_id
        # Calculate GST & Electric Duty
        gst_amount = (variable_charges * gst_rate) / 100
        electric_duty_amount = (variable_charges * electric_duty) / 100

        # Compute Final Total Surcharge
        computed_surcharge = total_monthly_surcharge + total_adjusted_surcharge
        gst_on_surcharge = (computed_surcharge * gst_rate) / 100
        electric_duty_on_surcharge = (computed_surcharge * electric_duty) / 100
        final_total_surcharge = computed_surcharge + gst_on_surcharge + electric_duty_on_surcharge

        # Compute Total Additional Charges
        total_additional_charges = gst_amount + electric_duty_amount

        # Compute Net Payable Amount
        net_payable_amount = variable_charges + final_total_surcharge + total_additional_charges

        # Fetch GST & Electric Duty IDs
        gst_id, electric_duty_id = fetch_gst_electric_duty_ids(cursor, gst_rate, electric_duty)

        # 🚨 Check if ReadingID already exists in AdditionalCharges
        cursor.execute("SELECT COUNT(*) FROM AdditionalCharges WHERE ReadingID = ?", (reading_id,))
        additional_charge_exists = cursor.fetchone()[0]

        if additional_charge_exists:
            st.warning(f"⚠️ Reading ID {reading_id} already exists in AdditionalCharges. Skipping insertion.")
            cursor.execute("SELECT AdditionalChargeID FROM AdditionalCharges WHERE ReadingID = ?", (reading_id,))
            additional_charge_id = cursor.fetchone()[0]  # Fetch existing ID
        else:
            # Insert Additional Charges
            cursor.execute("""
                INSERT INTO AdditionalCharges (ReadingID, GSTID, ElectricDutyID,GST,ElectricDuty)
                VALUES (?, ?, ?,?,?)
            """, (reading_id, gst_id, electric_duty_id,gst_amount,electric_duty_amount))

            cursor.execute("SELECT last_insert_rowid()")
            additional_charge_id = cursor.fetchone()[0]

        # 🚨 Check if ReadingID already exists in SurchargeGSTDuty
        cursor.execute("SELECT COUNT(*) FROM SurchargeGSTDuty WHERE ReadingID = ?", (reading_id,))
        surcharge_exists = cursor.fetchone()[0]

        if surcharge_exists:
            st.warning(f"⚠️ Reading ID {reading_id} already exists in SurchargeGSTDuty. Skipping insertion.")
            cursor.execute("SELECT SurchargeGSTDutyID FROM SurchargeGSTDuty WHERE ReadingID = ?", (reading_id,))
            surcharge_gst_duty_id = cursor.fetchone()[0]  # Fetch existing ID
        else:
            # Insert Surcharge, GST, and Duty
            cursor.execute("""
                INSERT INTO SurchargeGSTDuty (ReadingID, MonthSurcharge, AdjustedSurcharge, TotalSurcharge,
                                              GSTID, ElectricDutyID, GSTAmount, ElectricDutyAmount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (reading_id, total_monthly_surcharge, total_adjusted_surcharge, computed_surcharge,
                  gst_id, electric_duty_id, gst_on_surcharge, electric_duty_on_surcharge))

            cursor.execute("SELECT last_insert_rowid()")
            surcharge_gst_duty_id = cursor.fetchone()[0]

        # 🚨 Check if ReadingID already exists in BillingCharges
        cursor.execute("SELECT COUNT(*) FROM BillingCharges WHERE ReadingID = ?", (reading_id,))
        billing_exists = cursor.fetchone()[0]

        if billing_exists:
            st.warning(f"⚠️ Reading ID {reading_id} already exists in BillingCharges. Skipping insertion.")
        else:
            # Insert Billing Charges
            cursor.execute("""
                INSERT INTO BillingCharges (ReadingID, RatePerUnit, VariableCharges, AdditionalChargeID, SurchargeGSTDutyID, 
                                           TotalAdditionalCharges, TotalSurcharge, NetPayableAmount, Status, Remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (reading_id, rate_per_unit, variable_charges, additional_charge_id, surcharge_gst_duty_id, 
                  total_additional_charges, final_total_surcharge, net_payable_amount, 'Due', 'No remarks'))

        # 📄 Generate PDF Bill
        pdf_path = generate_pdf(flat_no, person_id, name, month, reading_date, previous_reading,
                                present_reading, units_consumed, electric_duty_amount, gst_amount, 
                                computed_surcharge, variable_charges, total_additional_charges, 
                                net_payable_amount)

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "📥 Download Bill PDF",
                    f,
                    file_name=os.path.basename(pdf_path),
                    mime="application/pdf"
                )
        else:
            st.error("❌ Error generating the PDF!")

        conn.commit()
        st.success("✅ Billing information added successfully!")

    except sqlite3.IntegrityError as e:
        st.error(f"❌ Database Error: {e}")

    except Exception as e:
        st.error(f"⚠️ Unexpected Error: {e}")

    finally:
        conn.close()


def fetch_complete_bill(flat_no, month):
    conn = sqlite3.connect("billing_system.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT br.ReadingID, br.PreviousReading, br.PresentReading, br.UnitsConsumed, br.UnitsAdjusted, 
               bc.BillID, bc.RatePerUnit, bc.VariableCharges, ac.ElectricDuty, ac.GST, 
               sdg.MonthSurcharge,sdg.AdjustedSurcharge
        FROM BillingReadings br
        JOIN BillingCharges bc ON br.ReadingID = bc.ReadingID
        JOIN SurchargeGSTDuty sdg ON br.ReadingID=sdg.ReadingID
        JOIN AdditionalCharges ac ON  br.ReadingID=ac.ReadingID
        WHERE br.FlatNo = ? AND br.BillingMonth = ?
        """, 
        (flat_no, month)
    )
    bill_data = cursor.fetchone()
    conn.close()
    return bill_data


def update_billing_readings(cursor, flat_no, month, present_reading, previous_reading):
    cursor.execute("""
        UPDATE BillingReadings 
        SET PresentReading=?, PreviousReading=? 
        WHERE FlatNo=? AND BillingMonth=?
    """, (present_reading, previous_reading, flat_no, month))


def update_billing_charges(cursor,bill_id,reading_id, rate_per_unit, variable_charges, total_additional_charges, total_surcharge, net_payable_amount):
    cursor.execute("""
        UPDATE BillingCharges 
        SET RatePerUnit=?, VariableCharges=?, TotalAdditionalCharges=?, TotalSurcharge=?, NetPayableAmount=?
        WHERE ReadingID=? AND BillID=?
    """, (rate_per_unit, variable_charges, total_additional_charges, total_surcharge, net_payable_amount, reading_id,bill_id))


def fetch_surcharge_mapping(cursor, reading_id, billing_month):
    """
    Fetch surcharge mappings from the ReadingSurchargeMapping table filtered by ReadingID and BillingMonth.
    
    Args:
        db_path (str): Path to SQLite database.
        reading_id (int): Filter by specific ReadingID.
        billing_month (str): Filter by specific BillingMonth (Format: 'YYYY-MM-DD').
    
    Returns:
        list: List of tuples containing surcharge mapping records.
    """
    
   
    query = """
        SELECT 
          rsm.SurchargeID, sr.SurchargeTypeID, S.TypeName, sr.RatePerUnit, 
          rsm.AdjustedBillingMonth, rsm.SurchargeAmount, rsm.AdjustmentReason, sr.EffectiveDate
        FROM ReadingSurchargeMapping rsm
        LEFT JOIN Surcharge sr ON rsm.SurchargeID = sr.SurchargeID
        LEFT JOIN SurchargeType S ON sr.SurchargeTypeID = S.SurchargeTypeID
        WHERE rsm.ReadingID = ? AND rsm.BillingMonth = ?

       """
    
    cursor.execute(query, (reading_id, billing_month))
    results = cursor.fetchall()
    print(f"Fetched Surcharge Data: {results}")  # Debugging Output
    return results

def update_bill(flat_no, month, present_reading=None, electric_duty=None, gst=None,unit_adjusted=None,total_montly_surcharge=None,total_adjusted_surcharge=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        bill_data = fetch_complete_bill(flat_no, month)
        if not bill_data:
            st.error(f"❌ No bill found for Flat {flat_no} in {month}")
            return

        (
        reading_id, previous_reading, old_present_reading, units_consumed,old_unit_adjusted,
        bill_id, old_rate_per_unit, variable_charges, old_electric_duty, old_gst, 
        old_total_monthly_surcharge,old_total_adjusted_surcharge
        ) = bill_data

        present_reading = present_reading 
        electric_duty = electric_duty 
        gst = gst 
        total_montly_surcharge=total_montly_surcharge 
        total_adjusted_surcharge=total_adjusted_surcharge 
        unit_adjusted=unit_adjusted 
        computed_surcharge=total_montly_surcharge+total_adjusted_surcharge

        units_consumed = calculate_units_consumed(previous_reading,present_reading)
        variable_charges = units_consumed * old_rate_per_unit
        
        gst_amount = (variable_charges * gst) / 100
        electric_duty_amount = (variable_charges * electric_duty) / 100
        total_additional_charges = gst_amount + electric_duty_amount
        net_payable_amount = variable_charges + total_additional_charges + computed_surcharge

        update_billing_readings(cursor, flat_no, month, present_reading, previous_reading)
        update_billing_charges(cursor,bill_id, reading_id, old_rate_per_unit, variable_charges, total_additional_charges, computed_surcharge, net_payable_amount)

        conn.commit()
        st.success(f"✅ Bill updated successfully for Flat {flat_no} ({month})!")
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error updating bill: {e}")
    finally:
        conn.close()

def delete_bill(flat_no, month):
    """Delete bill records from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        bill_data = fetch_complete_bill(flat_no, month)
        if not bill_data:
            st.error(f"❌ No bill found for Flat {flat_no} in {month}!")
            return

        reading_id, _, _, _, _, bill_id, _, _, _, _, _, _ = bill_data

        # Delete from dependent tables first
        cursor.execute("DELETE FROM BillingCharges WHERE BillID = ?", (bill_id,))
        cursor.execute("DELETE FROM BillingReadings WHERE ReadingID = ?", (reading_id,))

        conn.commit()
        st.success(f"✅ Bill record for Flat {flat_no} ({month}) deleted successfully!")
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error deleting bill: {e}")
    finally:
        conn.close()

def update_bill_status(bill_id, status):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE BillingCharges 
            SET Status=? 
            WHERE BillID=?
        """, (status, bill_id))

        conn.commit()
        st.success(f"✅ Bill status updated successfully to '{status}'!")

    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error updating bill status: {e}")

    finally:
        conn.close()

def get_consumption_history(person_id=None, flat_no=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT ch.ConsumptionID, u.Name, ch.FlatNo, ch.BillingMonth, ch.UnitsConsumed, ch.RecordedAt
        FROM ConsumptionHistory ch
        JOIN Users u ON u.PersonID = ch.PersonID
        WHERE 1=1
    """
    params = []
    
    if person_id:
        query += " AND ch.PersonID = ?"
        params.append(person_id)
    if flat_no:
        query += " AND ch.FlatNo = ?"
        params.append(flat_no)

    query += " ORDER BY ch.BillingMonth DESC"

    df = pd.read_sql_query(query, conn, params=params)
    
    conn.close()
    return df




#Ashhad's Addition

# Fetch billing data from SQLite for the selected month
def fetch_billing_data(selected_month):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT br.FlatNo, u.Name, br.PreviousReading, br.PresentReading, 
               br.UnitsConsumed, br.BillingMonth, bc.RatePerUnit, 
               bc.VariableCharges, ac.GSTID, g.GST, ac.ElectricDutyID, ed.ElectricDuty, 
               sgd.TotalSurcharge, sgd.FuelChargeAdjustment, bc.NetPayableAmount
        FROM BillingReadings br
        JOIN BillingCharges bc ON br.ReadingID = bc.ReadingID
        JOIN AdditionalCharges ac ON bc.AdditionalChargeID = ac.AdditionalChargeID
        JOIN GSTRates g ON ac.GSTID = g.GSTID
        JOIN ElectricDutyRates ed ON ac.ElectricDutyID = ed.DutyID
        JOIN SurchargeGSTDuty sgd ON bc.SurchargeGSTDutyID = sgd.SurchargeGSTDutyID
        JOIN Users u ON u.PersonID = br.PersonID
        WHERE br.BillingMonth = ?
    """, (selected_month,))
    
    data = cursor.fetchall()
    conn.close()
    return data


def Generate_bulk_bill_pdf(billing_data, selected_month):
    """Generate a multi-page PDF with bills for all flats in a selected month."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    
    for idx, bill in enumerate(billing_data):
        flat_no, name, prev_read, pres_read, units, month, rate, var_charges, gst_id, gst, duty_id, duty, surcharge, fuel_charge, payable = bill
        
        # PDF Layout
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(200, 750, "ELECTRIC BILL FOR NED STAFF COLONY")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, 720, f"Flat No: {flat_no}")
        pdf.drawString(50, 700, f"Name: {name}")
        pdf.drawString(50, 680, f"Billing Month: {selected_month}")
        
        # Bill Details Table
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, 640, "Units Details")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, 620, f"Previous Reading: {prev_read}")
        pdf.drawString(50, 600, f"Present Reading: {pres_read}")
        pdf.drawString(50, 580, f"Units Consumed: {units}")
        pdf.drawString(50, 560, f"Rate per Unit: {rate}")
        
        # Charges Section
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, 530, "Charges Details (PKR)")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, 510, f"Variable Charges: {var_charges}")
        pdf.drawString(50, 490, f"Electric Duty ({duty}%): {round(var_charges * duty / 100, 2)}")
        pdf.drawString(50, 470, f"GST ({gst}%): {round(var_charges * gst / 100, 2)}")
        pdf.drawString(50, 450, f"Surcharge: {surcharge}")
        pdf.drawString(50, 430, f"Fuel Charge Adjustment: {fuel_charge}")
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, 400, f"Total Payable Amount: {payable}")
        
        # Page Break
        if idx < len(billing_data) - 1:
            pdf.showPage()
    
    pdf.save()
    buffer.seek(0)
    return buffer

# ✅ Fetch GST Rates
def get_gst_rates():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM GSTRates ORDER BY EffectiveDate DESC", conn)
    conn.close()
    return df

# ✅ Fetch Electric Duty Rates
def get_electric_duty_rates():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM ElectricDutyRates ORDER BY EffectiveDate DESC", conn)
    conn.close()
    return df

# ✅ Fetch Surcharge Rates
def get_surcharge_rates():
    conn = get_connection()
    query = """
        SELECT 
            Surcharge.SurchargeID,
            SurchargeType.SurchargeTypeID,
            Surcharge.RatePerUnit,
            Surcharge.UnitsFrom,
            Surcharge.UnitsTo,
            Surcharge.EffectiveDate
        FROM Surcharge
        JOIN SurchargeType ON Surcharge.SurchargeTypeID = SurchargeType.SurchargeTypeID
        ORDER BY Surcharge.EffectiveDate DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
# ✅ Insert or Update GST Rate
def upsert_gst_rate(value, effective_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO GSTRates (EffectiveDate, GST)
        VALUES (?, ?)
        ON CONFLICT(EffectiveDate) DO UPDATE SET GST = excluded.GST;
    """, (effective_date, value))
    conn.commit()
    conn.close()

# ✅ Insert or Update Electric Duty Rate
def upsert_electric_duty_rate(value, effective_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ElectricDutyRates (EffectiveDate, ElectricDuty)
        VALUES (?, ?)
        ON CONFLICT(EffectiveDate) DO UPDATE SET ElectricDuty = excluded.ElectricDuty;
    """, (effective_date, value))
    conn.commit()
    conn.close()

# ✅ Insert or Update Surcharge Rate
def upsert_surcharge_rate(surcharge_type_id, rate_per_unit, units_from=None, units_to=None, effective_date=None):
    conn = get_connection()
    cursor = conn.cursor()

    # Default to today's date if not provided
    if effective_date is None:
        effective_date = datetime.today().strftime("%m/%d/%Y")

    cursor.execute("""
        INSERT INTO Surcharge (SurchargeTypeID, RatePerUnit, UnitsFrom, UnitsTo, EffectiveDate)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(SurchargeTypeID, EffectiveDate, UnitsFrom, UnitsTo) 
        DO UPDATE SET RatePerUnit = excluded.RatePerUnit;
    """, (surcharge_type_id, rate_per_unit, units_from, units_to, effective_date))

    conn.commit()
    conn.close()


from datetime import datetime
import sqlite3

import sqlite3
from datetime import datetime

def fetch_surcharge_rate(cursor,surcharge_type_id, units_consumed, effective_date=None):
    print(f"Fetching rate for SurchargeTypeID {surcharge_type_id}, Units {units_consumed}, Effective Date {effective_date}")

    # Convert surcharge_type_id to a regular int
    surcharge_type_id = int(surcharge_type_id)  

    conn = sqlite3.connect("billing_system.db")  
    cursor = conn.cursor()

    # Step 1: Get Latest Effective Date
    if not effective_date:
        today_date = datetime.today().strftime("%m/%d/%Y")  
        cursor.execute("""
            SELECT MAX(EffectiveDate) FROM Surcharge 
            WHERE SurchargeTypeID = ? 
            AND EffectiveDate <= ?
        """, (surcharge_type_id, today_date))
        
        effective_date = cursor.fetchone()[0]
        
        if not effective_date:  
            print(f"❌ No effective date found for SurchargeTypeID {surcharge_type_id}")
            return 0.0  

    # Convert effective_date to match DB format
    #effective_date = datetime.strptime(effective_date, "%m/%d/%Y").strftime("%Y-%m-%d")

    print(f"✅ Using Effective Date: {effective_date}")

    # Step 2: Fetch the applicable RatePerUnit
    cursor.execute("""
        SELECT SurchargeID, RatePerUnit FROM Surcharge
        WHERE SurchargeTypeID = ?
        AND EffectiveDate = ?
        AND (
            (UnitsFrom IS NULL AND UnitsTo IS NULL) OR
            (CAST(? AS REAL) BETWEEN CAST(UnitsFrom AS REAL) AND CAST(UnitsTo AS REAL)) OR
            (UnitsFrom IS NULL AND CAST(? AS REAL) <= CAST(UnitsTo AS REAL)) OR
            (CAST(? AS REAL) >= CAST(UnitsFrom AS REAL) AND UnitsTo IS NULL)
         )
         ORDER BY EffectiveDate DESC
         LIMIT 1
          """, (surcharge_type_id, effective_date, units_consumed, units_consumed, units_consumed))

    data = cursor.fetchone()  # Fetch a single row

    return data if data else print("None")  # Return None if no data found

