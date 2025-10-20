from flask import Flask, render_template, request, redirect, url_for, jsonify

from datetime import datetime
import mysql.connector

import itertools

app = Flask(__name__)

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "password", #my password is masked
    "database": "clinic"
}


def get_db_connection():
    return mysql.connector.connect(**db_config)

# page routes

@app.route("/")
def base():
    return redirect(url_for("newguest"))


@app.route("/newguest", methods=["GET", "POST"])
def newguest():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        typ = request.form.get("type", "W") # 'W' or 'A'

        conn = get_db_connection()
        print(conn)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO guests (name, phone, type) VALUES (%s, %s, %s)",
            (name, phone, typ)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("base"))
    return render_template("newguest.html")


@app.route("/guests")
def guests():
    # Load all guests
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM guests ORDER BY created_at DESC")
    all_guests = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("guests.html", guests=all_guests)

@app.route("/doctorsview")
def doctorsview():
    # Load all doctors
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM dr_room")
    all_doctors = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("doctorsview.html", dr_room=all_doctors)

@app.route("/update_doctor_status/<room_no>", methods=["POST"])
def update_doctor_status_form(room_no):
    """Updates doctor status via form submission."""
    new_status = request.form.get("new_status")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dr_room
        SET dr_status = %s
        WHERE room_no = %s
    """, (new_status, room_no))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/doctorsview")


@app.route("/update_doctor_status_json", methods=["POST"])
def update_doctor_status_json():
    """Updates doctor status via JavaScript (AJAX) request."""
    data = request.get_json()
    room_no = data["room_no"]
    status = data["status"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE dr_room
        SET dr_status = %s
        WHERE room_no = %s
    """, (status, room_no))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify(success=True)



@app.route("/history")
def history():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM history")
    all_entries = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("history.html", historytable=all_entries)



@app.route("/update_req_dr", methods=["POST"])
def update_req_dr():
    data = request.get_json()
    guest_id = data.get("id")
    req_dr = data.get("req_dr")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE guests SET req_dr=%s WHERE id=%s",
            (req_dr, guest_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        return jsonify({"success": False})
    

@app.route("/common_page")
def common_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Only guests with a doctor assigned
    cursor.execute("""
        SELECT *
        FROM guests g
        WHERE g.called_status= 1 
        ORDER BY g.created_at ASC
    """)
    patients = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("common_page.html", patientlist=patients)


@app.route("/assign_doctor", methods=["GET", "POST"])
def assign_doctor():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Load guests
    cursor.execute("SELECT * FROM guests ORDER BY created_at ASC")
    guests_list = cursor.fetchall()

    # Load doctors
    cursor.execute("SELECT * FROM dr_room ORDER BY room_no ASC")
    doctors = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template("assign_doctor.html", guests=guests_list, doctors=doctors)


@app.route("/update_req_dr", methods=["POST"])
def update_req_dr_reception():
    data = request.get_json()
    guest_id = data.get("id")
    req_dr = data.get("req_dr")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE guests SET req_dr = %s WHERE id = %s", (req_dr, guest_id))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True})


@app.route("/update_guest_status", methods=["POST"])
def update_guest_status():
    data = request.get_json()
    guest_id = data.get("id")
    new_status = data.get("status")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get guest info
    cursor.execute("SELECT * FROM guests WHERE id = %s", (guest_id,))
    guest = cursor.fetchone()

    if not guest:
        cursor.close()
        conn.close()
        return jsonify({"success": False, "error": "Guest not found"})

    req_dr = guest["req_dr"]

    # When patient is called
    if new_status == "called":
        cursor.execute("""
            UPDATE guests 
            SET guest_status='called', called_status=TRUE 
            WHERE id=%s
        """, (guest_id,))
        cursor.execute("""
            UPDATE dr_room 
            SET dr_status='live' 
            WHERE room_no=%s
        """, (req_dr,))

    # When patient is done
    elif new_status == "done":
        # Only free the doctor if the patient was ever called
        if guest["called_status"] == 1:
            cursor.execute("""
                UPDATE dr_room 
                SET dr_status='free' 
                WHERE room_no=%s
            """, (req_dr,))

        # Add patient to history table
        cursor.execute("""
            INSERT INTO history (name, room_visited)
            VALUES (%s, %s)
        """, (guest["name"], req_dr))

        # Remove from guests table
        cursor.execute("DELETE FROM guests WHERE id=%s", (guest_id,))

    else:
        # Just update the guest status field
        cursor.execute("""
            UPDATE guests 
            SET guest_status=%s 
            WHERE id=%s
        """, (new_status, guest_id))

    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"success": True})



@app.route('/update_patient_status/<int:patient_id>', methods=['POST'])
def update_patient_status(patient_id):
    data = request.get_json()
    new_status = data['status']
    doctor_id = data.get('doctor_id')

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    if new_status == 'called':
        cursor.execute("UPDATE guests SET status='called', called_status=TRUE WHERE id=%s", (patient_id,))
        cursor.execute("UPDATE doctors SET status='live' WHERE id=%s", (doctor_id,))

    elif new_status == 'done':
        cursor.execute("SELECT called_status, doctor_id FROM guests WHERE id=%s", (patient_id,))
        row = cursor.fetchone()
        if row and row['called_status']:
            cursor.execute("UPDATE doctors SET status='free' WHERE id=%s", (row['doctor_id'],))
        cursor.execute("INSERT INTO history SELECT * FROM guests WHERE id=%s", (patient_id,))
        cursor.execute("DELETE FROM guests WHERE id=%s", (patient_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'success': True})


if __name__ == "__main__":
    app.run(debug=True)


