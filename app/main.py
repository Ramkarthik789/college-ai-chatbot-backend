from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import engine, Base, SessionLocal
from app import models, schemas
from app.auth import create_access_token, verify_token
from pypdf import PdfReader
import os
import shutil
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
print("LOADED MAIN FROM:",__file__)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
@app.get("/cors-test")
def cors_test():
    return{"message": "backend working"}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)




# 🔥 ADD HERE
def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    reader = PdfReader(file_path)

    max_pages = min(15, len(reader.pages))  # 🔥 Only first 15 pages

    for i in range(max_pages):
        page = reader.pages[i]
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text

@app.get("/")
def home():
    return {"message": "College chatbot backend running 🔥"}


# -------------------------
# Student APIs
# -------------------------
def require_hod(user=Depends(verify_token)):
    if user["role"] != "hod":
        raise HTTPException(status_code=403, detail="Only HOD can perform this action")
    return user
@app.post("/students/")
def create_student(student: schemas.StudentCreate, db: Session = Depends(get_db)):
    existing_email = db.query(models.Student).filter(models.Student.email == student.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    existing_roll = db.query(models.Student).filter(models.Student.roll_number == student.roll_number).first()
    if existing_roll:
        raise HTTPException(status_code=400, detail="Roll number already exists")

    new_student = models.Student(
        name=student.name,
        email=student.email,
        roll_number=student.roll_number,
        password=hash_password(student.password),
        branch=student.branch,
        role=student.role
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    return {
        "message": "Student created successfully",
        "student_id": new_student.id
    }


@app.post("/login/")
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.Student).filter(models.Student.email == data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Wrong password")

    token = create_access_token({
    "sub": user.email,
    "role": user.role
})

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@app.get("/me/")
def get_current_user(db: Session = Depends(get_db), user=Depends(verify_token)):
    user_email = user["email"]

    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": student.id,
        "name": student.name,
        "email": student.email,
        "roll_number": student.roll_number,
        "branch": student.branch,
        "role": student.role
    }

# -------------------------
# Result APIs
# -------------------------

@app.post("/results/")
def create_result(result_data: schemas.ResultCreate, db: Session = Depends(get_db), user=Depends(require_hod)):
    student = db.query(models.Student).filter(models.Student.id == result_data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    new_result = models.Result(
        student_id=result_data.student_id,
        semester=result_data.semester,
        exam_month=result_data.exam_month,
        exam_year=result_data.exam_year,
        sgpa=result_data.sgpa,
        cgpa=result_data.cgpa
    )

    db.add(new_result)
    db.commit()
    db.refresh(new_result)

    for sub in result_data.subjects:
        subject_row = models.SubjectResult(
            result_id=new_result.id,
            subject_code=sub.subject_code,
            subject_name=sub.subject_name,
            external_marks=sub.external_marks,
            grade=sub.grade,
            grade_points=sub.grade_points,
            credits=sub.credits,
            subject_type=sub.subject_type
        )
        db.add(subject_row)

    db.commit()

    return {
        "message": "Result added successfully",
        "result_id": new_result.id
    }


@app.get("/students/{student_id}/results")
def get_student_results(student_id: int, db: Session = Depends(get_db), user: str = Depends(verify_token)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    results = db.query(models.Result).filter(models.Result.student_id == student_id).all()

    output = []
    for result in results:
        subjects = db.query(models.SubjectResult).filter(models.SubjectResult.result_id == result.id).all()

        output.append({
            "result_id": result.id,
            "semester": result.semester,
            "exam_month": result.exam_month,
            "exam_year": result.exam_year,
            "sgpa": result.sgpa,
            "cgpa": result.cgpa,
            "subjects": [
                {
                    "subject_code": s.subject_code,
                    "subject_name": s.subject_name,
                    "external_marks": s.external_marks,
                    "grade": s.grade,
                    "grade_points": s.grade_points,
                    "credits": s.credits,
                    "subject_type": s.subject_type
                }
                for s in subjects
            ]
        })

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "results": output
    }


@app.get("/students/{student_id}/cgpa")
def get_student_cgpa(student_id: int, db: Session = Depends(get_db), user: str = Depends(verify_token)):
    latest_result = (
        db.query(models.Result)
        .filter(models.Result.student_id == student_id)
        .order_by(models.Result.id.desc())
        .first()
    )

    if not latest_result:
        raise HTTPException(status_code=404, detail="No result found for student")

    return {
        "student_id": student_id,
        "semester": latest_result.semester,
        "cgpa": latest_result.cgpa,
        "sgpa": latest_result.sgpa
    }


@app.get("/students/{student_id}/subject-grade")
def get_subject_grade(student_id: int, subject_name: str, db: Session = Depends(get_db), user: str = Depends(verify_token)):
    subject = (
        db.query(models.SubjectResult)
        .join(models.Result, models.SubjectResult.result_id == models.Result.id)
        .filter(models.Result.student_id == student_id)
        .filter(models.SubjectResult.subject_name.ilike(f"%{subject_name}%"))
        .first()
    )

    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    return {
        "student_id": student_id,
        "subject_name": subject.subject_name,
        "grade": subject.grade,
        "external_marks": subject.external_marks,
        "grade_points": subject.grade_points,
        "credits": subject.credits
    }
@app.get("/my-result")
def my_result(db: Session = Depends(get_db), user_email: str = Depends(verify_token)):
    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    results = db.query(models.Result).filter(models.Result.student_id == student.id).all()

    output = []
    for result in results:
        subjects = db.query(models.SubjectResult).filter(models.SubjectResult.result_id == result.id).all()

        output.append({
            "result_id": result.id,
            "semester": result.semester,
            "exam_month": result.exam_month,
            "exam_year": result.exam_year,
            "sgpa": result.sgpa,
            "cgpa": result.cgpa,
            "subjects": [
                {
                    "subject_code": s.subject_code,
                    "subject_name": s.subject_name,
                    "external_marks": s.external_marks,
                    "grade": s.grade,
                    "grade_points": s.grade_points,
                    "credits": s.credits,
                    "subject_type": s.subject_type
                }
                for s in subjects
            ]
        })

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "results": output
    }


@app.get("/my-cgpa")
def my_cgpa(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    user_email = user["email"]

    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    latest_result = (
        db.query(models.Result)
        .filter(models.Result.student_id == student.id)
        .order_by(models.Result.id.desc())
        .first()
    )

    if not latest_result:
        raise HTTPException(status_code=404, detail="No result found")

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "cgpa": latest_result.cgpa,
        "sgpa": latest_result.sgpa,
        "semester": latest_result.semester
    }

@app.get("/my-attendance")
def my_attendance(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    user_email = user["email"]

    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "attendance_percentage": student.attendance_percentage
    }

@app.get("/my-lab-grades")
def my_lab_grades(db: Session = Depends(get_db), user_email: str = Depends(verify_token)):
    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    lab_subjects = (
        db.query(models.SubjectResult)
        .join(models.Result, models.SubjectResult.result_id == models.Result.id)
        .filter(models.Result.student_id == student.id)
        .filter(models.SubjectResult.subject_type.ilike("%lab%"))
        .all()
    )

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "lab_subjects": [
            {
                "subject_name": s.subject_name,
                "grade": s.grade,
                "external_marks": s.external_marks,
                "grade_points": s.grade_points,
                "credits": s.credits
            }
            for s in lab_subjects
        ]
    }
@app.post("/chatbot/query")
def chatbot_query(
    query: schemas.ChatQuery,
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    user_email = user["email"]

    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    message = query.message.lower().strip()
    # 1. CGPA / SGPA
    if "cgpa" in message or "sgpa" in message:
        latest_result = (
            db.query(models.Result)
            .filter(models.Result.student_id == student.id)
            .order_by(models.Result.id.desc())
            .first()
        )

        if not latest_result:
            raise HTTPException(status_code=404, detail="No result found")

        if "cgpa" in message and "sgpa" in message:
            return {
                "reply": f"Your latest SGPA is {latest_result.sgpa} and CGPA is {latest_result.cgpa}."
            }
        elif "cgpa" in message:
            return {
                "reply": f"Your current CGPA is {latest_result.cgpa}."
            }
        else:
            return {
                "reply": f"Your latest SGPA is {latest_result.sgpa}."
            }

    # 2. Full result
    elif "result" in message:
        results = db.query(models.Result).filter(models.Result.student_id == student.id).all()

        output = []
        for result in results:
            subjects = db.query(models.SubjectResult).filter(
                models.SubjectResult.result_id == result.id
            ).all()

            output.append({
                "semester": result.semester,
                "exam_month": result.exam_month,
                "exam_year": result.exam_year,
                "sgpa": result.sgpa,
                "cgpa": result.cgpa,
                "subjects": [
                    {
                        "subject_name": s.subject_name,
                        "external_marks": s.external_marks,
                        "grade": s.grade,
                        "subject_type": s.subject_type
                    }
                    for s in subjects
                ]
            })

        return {
            "reply": "Here is your full result.",
            "student_name": student.name,
            "roll_number": student.roll_number,
            "results": output
        }

    # 3. Lab grades
    elif "lab" in message and "grade" in message:
        lab_subjects = (
            db.query(models.SubjectResult)
            .join(models.Result, models.SubjectResult.result_id == models.Result.id)
            .filter(models.Result.student_id == student.id)
            .filter(models.SubjectResult.subject_type.ilike("%lab%"))
            .all()
        )

        if not lab_subjects:
            return {"reply": "No lab subjects found in your result."}

        return {
            "reply": "These are your lab grades.",
            "lab_subjects": [
                {
                    "subject_name": s.subject_name,
                    "grade": s.grade,
                    "external_marks": s.external_marks
                }
                for s in lab_subjects
            ]
        }

    # 4. Subject-specific grade
    elif "grade" in message:
        subject_keywords = {
            "mmd": "Mining Massive Datasets",
            "mining massive datasets": "Mining Massive Datasets",
            "social media analytics": "Social Media Analytics",
            "sma": "Social Media Analytics",
            "data visualization": "Data Visualization Techniques",
            "dvt": "Data Visualization Techniques",
            "organizational behavior": "Organizational Behavior",
            "marketing management": "Marketing Management",
            "mean stack": "MEAN Stack Technologies",
            "universal human values": "Universal Human Values-II"
        }

        matched_subject = None
        for key, value in subject_keywords.items():
            if key in message:
                matched_subject = value
                break

        if not matched_subject:
            return {
                "reply": "Please mention the subject name clearly. Example: 'What grade did I get in MMD?'"
            }

        subject = (
            db.query(models.SubjectResult)
            .join(models.Result, models.SubjectResult.result_id == models.Result.id)
            .filter(models.Result.student_id == student.id)
            .filter(models.SubjectResult.subject_name.ilike(f"%{matched_subject}%"))
            .first()
        )

        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        return {
            "reply": f"You got {subject.grade} grade in {subject.subject_name}. Your external marks are {subject.external_marks}."
        }

    # 5. External marks
    elif "external" in message and "marks" in message:
        latest_result = (
            db.query(models.Result)
            .filter(models.Result.student_id == student.id)
            .order_by(models.Result.id.desc())
            .first()
        )

        if not latest_result:
            raise HTTPException(status_code=404, detail="No result found")

        subjects = db.query(models.SubjectResult).filter(
            models.SubjectResult.result_id == latest_result.id
        ).all()

        return {
            "reply": "These are your external marks.",
            "subjects": [
                {
                    "subject_name": s.subject_name,
                    "external_marks": s.external_marks
                }
                for s in subjects
            ]
        }
        # 6. Attendance
    elif "attendance" in message:
        if student.attendance_percentage is None:
            return {"reply": "Attendance data not available."}

        return {
            "reply": f"Your current attendance is {student.attendance_percentage}%."
        }

    # 7. Fees
    elif "fee" in message or "fees" in message:
        if student.total_fee is None:
            return {"reply": "Fee details not available."}

        if "pending" in message or "due" in message or "left" in message:
            return {
                "reply": f"Your pending fee is {student.pending_fee}."
            }

        elif "paid" in message:
            return {
                "reply": f"You have paid {student.paid_fee}."
            }

        elif "total" in message:
            return {
                "reply": f"Your total fee is {student.total_fee}."
            }

        else:
            return {
                "reply": f"Your total fee is {student.total_fee}, paid fee is {student.paid_fee}, and pending fee is {student.pending_fee}."
            }
        # 8. Faculty list
    elif "faculty list" in message or "show faculty" in message or "all faculty" in message:
        faculty_list = db.query(models.Faculty).all()

        if not faculty_list:
            return {"reply": "No faculty data available."}

        return {
            "reply": "Here is the faculty list.",
            "faculty": [
                {
                    "name": f.name,
                    "subject": f.subject,
                    "designation": f.designation,
                    "room_number": f.room_number,
                    "status": f.status
                }
                for f in faculty_list
            ]
        }

    # 9. Faculty by subject
    elif "who teaches" in message or "faculty for" in message or "who is teaching" in message:
        subject_keywords = {
            "mmd": "Mining Massive Datasets",
            "mining massive datasets": "Mining Massive Datasets",
            "social media analytics": "Social Media Analytics",
            "sma": "Social Media Analytics",
            "data visualization": "Data Visualization Techniques",
            "dvt": "Data Visualization Techniques",
            "organizational behavior": "Organizational Behavior",
            "marketing management": "Marketing Management",
            "mean stack": "MEAN Stack Technologies",
            "universal human values": "Universal Human Values-II"
        }

        matched_subject = None
        for key, value in subject_keywords.items():
            if key in message:
                matched_subject = value
                break

        if not matched_subject:
            return {
                "reply": "Please mention the subject name clearly. Example: 'Who teaches MMD?'"
            }

        faculty = db.query(models.Faculty).filter(
            models.Faculty.subject.ilike(f"%{matched_subject}%")
        ).first()

        if not faculty:
            return {"reply": f"No faculty information found for {matched_subject}."}

        return {
            "reply": f"{faculty.name} teaches {faculty.subject}. {faculty.designation}, room {faculty.room_number}, currently {faculty.status}."
        }

    # 10. Faculty availability / location
    elif "where is" in message or "is" in message and ("available" in message or "sir" in message or "madam" in message):
        faculty_list = db.query(models.Faculty).all()

        matched_faculty = None
        for f in faculty_list:
            faculty_name_lower = f.name.lower()
            if any(word in message for word in faculty_name_lower.split()):
                matched_faculty = f
                break

        if not matched_faculty:
            return {
                "reply": "Please mention the faculty name clearly. Example: 'Where is Srikanth sir?'"
            }

        return {
            "reply": f"{matched_faculty.name} is currently {matched_faculty.status}. Room: {matched_faculty.room_number}. Note: {matched_faculty.availability_note}."
        }
        # 11. Notes / Study Materials
        # 11. Notes / Study Materials
    elif "notes" in message or "paper" in message or "manual" in message or "file" in message:
        subject_keywords = {
            "mmd": "Mining Massive Datasets",
            "mining massive datasets": "Mining Massive Datasets",
            "social media analytics": "Social Media Analytics",
            "sma": "Social Media Analytics",
            "data visualization techniques": "Data visualization techniques",
            "data visualization": "Data visualization techniques",
            "dvt": "Data visualization techniques",
            "organizational behavior": "Organizational Behavior",
            "marketing management": "Marketing Management",
            "mean stack": "MEAN Stack Technologies",
            "universal human values": "Universal Human Values-II"
        }

        matched_subject = None
        for key, value in subject_keywords.items():
            if key in message:
                matched_subject = value
                break

        if not matched_subject:
            return {
                "reply": "Please mention the subject name clearly. Example: 'Give MMD notes' or 'Give DVT file'."
            }

        materials = db.query(models.StudyMaterial).all()

        matched_materials = []
        for m in materials:
            if m.subject_name and m.subject_name.lower().strip() == matched_subject.lower().strip():
                matched_materials.append(m)

        if not matched_materials:
            return {
                "reply": f"No study materials found for {matched_subject}."
            }

        return {
            "reply": f"I found study materials for {matched_subject}.",
            "materials": [
                {
                    "title": m.title,
                    "document_type": m.document_type,
                    "file_name": m.file_name,
                    "download_url": f"/materials/{m.id}/download"
                }
                for m in matched_materials
            ]
        }
        # Syllabus
        # 12. Syllabus
        # 12. Syllabus
        # 12. Syllabus (SMART SEARCH)
    elif "syllabus" in message or "unit" in message or "subject" in message:
        syllabus = db.query(models.SyllabusDocument).first()

        if not syllabus:
            return {"reply": "No syllabus uploaded yet."}

        text = syllabus.extracted_text.lower()

        # Clean message
        message = message.lower()

        # Remove common useless words
        stop_words = ["what", "is", "the", "give", "show", "syllabus", "of", "for", "in"]
        keywords = [w for w in message.split() if w not in stop_words and len(w) > 2]

        if not keywords:
            return {
                "reply": f"Showing general syllabus from '{syllabus.title}':",
                "content": syllabus.extracted_text[:1500]
            }

        # Split into chunks (better than \n\n)
        sections = text.split("\n")

        best_section = ""
        best_score = 0

        for sec in sections:
            score = 0
            for word in keywords:
                if word in sec:
                    score += 2   # give more weight

            if score > best_score:
                best_score = score
                best_section = sec

        if best_score == 0:
            return {
                "reply": "I couldn't find exact match, showing general syllabus:",
                "content": syllabus.extracted_text[:1500]
            }

        return {
            "reply": f"I found this in syllabus '{syllabus.title}':",
            "content": best_section
        }
    else:
       return {
            "reply": "Sorry, I could not understand your question. Try asking: 'What is my CGPA?', 'Show my result', or 'What grade did I get in MMD?','what is my attendance?','how much fee is pending?'"
        }
@app.put("/students/{student_id}/attendance")
def update_attendance(
    student_id: int,
    data: schemas.AttendanceUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(require_hod)
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.attendance_percentage = data.attendance_percentage
    db.commit()
    db.refresh(student)

    return {
        "message": "Attendance updated successfully",
        "student_id": student.id,
        "attendance_percentage": student.attendance_percentage
    }
@app.put("/students/{student_id}/fees")
def update_fees(
    student_id: int,
    data: schemas.FeesUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(require_hod)
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.total_fee = data.total_fee
    student.paid_fee = data.paid_fee
    student.pending_fee = data.total_fee - data.paid_fee

    db.commit()
    db.refresh(student)

    return {
        "message": "Fees updated successfully",
        "student_id": student.id,
        "total_fee": student.total_fee,
        "paid_fee": student.paid_fee,
        "pending_fee": student.pending_fee
    }
@app.get("/my-attendance")
def my_attendance(
    db: Session = Depends(get_db),
    user_email: str = Depends(verify_token)
):
    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "attendance_percentage": student.attendance_percentage
    }
@app.get("/my-fees")
def my_fees(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    user_email = user["email"]

    student = db.query(models.Student).filter(models.Student.email == user_email).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "student_name": student.name,
        "roll_number": student.roll_number,
        "total_fee": student.total_fee,
        "paid_fee": student.paid_fee,
        "pending_fee": student.pending_fee
    }
@app.post("/faculty/")
def create_faculty(
    faculty: schemas.FacultyCreate,
    db: Session = Depends(get_db),
    user: str = Depends(require_hod)
):
    new_faculty = models.Faculty(
        name=faculty.name,
        email=faculty.email,
        department=faculty.department,
        subject=faculty.subject,
        designation=faculty.designation,
        room_number=faculty.room_number,
        status=faculty.status,
        availability_note=faculty.availability_note
    )

    db.add(new_faculty)
    db.commit()
    db.refresh(new_faculty)

    return {
        "message": "Faculty created successfully",
        "faculty_id": new_faculty.id
    }
@app.get("/faculty/")
def get_all_faculty(
    db: Session = Depends(get_db),
    user: str = Depends(verify_token)
):
    faculty_list = db.query(models.Faculty).all()

    return [
        {
            "id": f.id,
            "name": f.name,
            "email": f.email,
            "department": f.department,
            "subject": f.subject,
            "designation": f.designation,
            "room_number": f.room_number,
            "status": f.status,
            "availability_note": f.availability_note
        }
        for f in faculty_list
    ]
@app.get("/faculty/search")
def search_faculty(
    name: str,
    db: Session = Depends(get_db),
    user: str = Depends(verify_token)
):
    faculty = db.query(models.Faculty).filter(models.Faculty.name.ilike(f"%{name}%")).all()

    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    return [
        {
            "id": f.id,
            "name": f.name,
            "subject": f.subject,
            "designation": f.designation,
            "room_number": f.room_number,
            "status": f.status,
            "availability_note": f.availability_note
        }
        for f in faculty
    ]
@app.put("/faculty/{faculty_id}/status")
def update_faculty_status(
    faculty_id: int,
    data: schemas.FacultyStatusUpdate,
    db: Session = Depends(get_db),
    user: str = Depends(require_hod)
):
    faculty = db.query(models.Faculty).filter(models.Faculty.id == faculty_id).first()

    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    faculty.status = data.status
    faculty.availability_note = data.availability_note
    faculty.room_number = data.room_number

    db.commit()
    db.refresh(faculty)

    return {
        "message": "Faculty status updated successfully",
        "faculty_id": faculty.id,
        "name": faculty.name,
        "status": faculty.status,
        "room_number": faculty.room_number,
        "availability_note": faculty.availability_note
    }
UPLOAD_DIR = "uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


@app.post("/materials/upload")
def upload_study_material(
    subject_name: str = Form(...),
    title: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    file_location = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_material = models.StudyMaterial(
        subject_name=subject_name,
        title=title,
        document_type=document_type,
        file_name=file.filename,
        file_path=file_location,
        uploaded_by=user["email"]
    )

    db.add(new_material)
    db.commit()
    db.refresh(new_material)

    return {
        "message": "Study material uploaded successfully",
        "material_id": new_material.id,
        "file_name": new_material.file_name
    }
@app.get("/materials/")
def get_all_materials(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    materials = db.query(models.StudyMaterial).all()

    return [
        {
            "id": m.id,
            "subject_name": m.subject_name,
            "title": m.title,
            "document_type": m.document_type,
            "file_name": m.file_name,
            "file_path": m.file_path,
            "uploaded_by": m.uploaded_by
        }
        for m in materials
    ]
@app.get("/materials/search")
def search_materials(
    subject_name: str,
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    materials = db.query(models.StudyMaterial).filter(
        models.StudyMaterial.subject_name.ilike(f"%{subject_name}%")
    ).all()

    if not materials:
        raise HTTPException(status_code=404, detail="No study materials found")

    return [
        {
            "id": m.id,
            "subject_name": m.subject_name,
            "title": m.title,
            "document_type": m.document_type,
            "file_name": m.file_name,
            "file_path": m.file_path
        }
        for m in materials
    ]
@app.get("/materials/{material_id}/download")
def download_material(
    material_id: int,
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    material = db.query(models.StudyMaterial).filter(models.StudyMaterial.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if not os.path.exists(material.file_path):
        raise HTTPException(status_code=404, detail="File not found on server")

    return FileResponse(
        path=material.file_path,
        filename=material.file_name,
        media_type="application/octet-stream"
    )
@app.post("/syllabus/upload")
def upload_syllabus(
    subject_name: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    try:
        # ✅ Validate file
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files allowed")

        # ✅ Create folder if not exists
        syllabus_dir = "uploads/syllabus"
        os.makedirs(syllabus_dir, exist_ok=True)

        # ✅ Save file
        file_location = os.path.join(syllabus_dir, file.filename)

        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # ✅ Extract limited text (FAST ⚡)
        extracted_text = extract_text_from_pdf(file_location)

        # ✅ Save to DB
        new_doc = models.SyllabusDocument(
            subject_name=subject_name,
            title=title,
            file_name=file.filename,
            file_path=file_location,
            extracted_text=extracted_text,
            uploaded_by=user["email"]
        )

        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        return {
            "message": "Syllabus uploaded successfully 🔥",
            "syllabus_id": new_doc.id,
            "subject_name": subject_name
        }

    except Exception as e:
        print("❌ SYLLABUS ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/syllabus/")
def get_all_syllabus(
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    docs = db.query(models.SyllabusDocument).all()

    return [
        {
            "id": d.id,
            "subject_name": d.subject_name,
            "title": d.title,
            "file_name": d.file_name,
            "uploaded_by": d.uploaded_by
        }
        for d in docs
    ]
@app.post("/syllabus/ask")
def ask_syllabus_question(
    data: schemas.SyllabusQuestion,
    db: Session = Depends(get_db),
    user=Depends(verify_token)
):
    doc = db.query(models.SyllabusDocument).filter(
        models.SyllabusDocument.subject_name.ilike(f"%{data.subject_name}%")
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Syllabus not found for this subject")

    text = doc.extracted_text.lower()
    question = data.question.lower()

    lines = doc.extracted_text.splitlines()
    matched_lines = []

    for line in lines:
        if any(word in line.lower() for word in question.split()):
            matched_lines.append(line)

    if not matched_lines:
        return {
            "reply": f"I found the syllabus for {doc.subject_name}, but I could not find an exact answer."
        }

    return {
        "reply": f"I found this in the syllabus for {doc.subject_name}:",
        "answer": "\n".join(matched_lines[:10])
    }
@app.put("/students/{student_id}")
def update_student(
    student_id: int,
    data: schemas.StudentUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if data.name is not None:
        student.name = data.name
    if data.email is not None:
        student.email = data.email
    if data.roll_number is not None:
        student.roll_number = data.roll_number
    if data.branch is not None:
        student.branch = data.branch
    if data.role is not None:
        student.role = data.role

    db.commit()
    db.refresh(student)

    return {
        "message": "Student updated successfully",
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "roll_number": student.roll_number,
            "branch": student.branch,
            "role": student.role
        }
    }
@app.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(student)
    db.commit()

    return {
        "message": "Student deleted successfully"
    }
@app.put("/results/{result_id}")
def update_result(
    result_id: int,
    data: schemas.ResultUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()

    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    if data.semester is not None:
        result.semester = data.semester
    if data.exam_month is not None:
        result.exam_month = data.exam_month
    if data.exam_year is not None:
        result.exam_year = data.exam_year
    if data.sgpa is not None:
        result.sgpa = data.sgpa
    if data.cgpa is not None:
        result.cgpa = data.cgpa

    db.commit()
    db.refresh(result)

    return {
        "message": "Result updated successfully",
        "result": {
            "id": result.id,
            "student_id": result.student_id,
            "semester": result.semester,
            "exam_month": result.exam_month,
            "exam_year": result.exam_year,
            "sgpa": result.sgpa,
            "cgpa": result.cgpa
        }
    }
@app.delete("/results/{result_id}")
def delete_result(
    result_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    result = db.query(models.Result).filter(models.Result.id == result_id).first()

    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    # Delete subjects first (important ⚠️)
    db.query(models.SubjectResult).filter(
        models.SubjectResult.result_id == result_id
    ).delete()

    # Then delete result
    db.delete(result)
    db.commit()

    return {
        "message": "Result deleted successfully"
    }
@app.put("/subject-results/{subject_result_id}")
def update_subject_result(
    subject_result_id: int,
    data: schemas.SubjectResultUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    subject_result = db.query(models.SubjectResult).filter(
        models.SubjectResult.id == subject_result_id
    ).first()

    if not subject_result:
        raise HTTPException(status_code=404, detail="Subject result not found")

    if data.subject_code is not None:
        subject_result.subject_code = data.subject_code
    if data.subject_name is not None:
        subject_result.subject_name = data.subject_name
    if data.external_marks is not None:
        subject_result.external_marks = data.external_marks
    if data.grade is not None:
        subject_result.grade = data.grade
    if data.grade_points is not None:
        subject_result.grade_points = data.grade_points
    if data.credits is not None:
        subject_result.credits = data.credits
    if data.subject_type is not None:
        subject_result.subject_type = data.subject_type

    db.commit()
    db.refresh(subject_result)

    return {
        "message": "Subject result updated successfully",
        "subject_result": {
            "id": subject_result.id,
            "result_id": subject_result.result_id,
            "subject_code": subject_result.subject_code,
            "subject_name": subject_result.subject_name,
            "external_marks": subject_result.external_marks,
            "grade": subject_result.grade,
            "grade_points": subject_result.grade_points,
            "credits": subject_result.credits,
            "subject_type": subject_result.subject_type
        }
    }
@app.put("/subject-results/{subject_result_id}")
def update_subject_result(
    subject_result_id: int,
    data: schemas.SubjectResultUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    subject_result = db.query(models.SubjectResult).filter(
        models.SubjectResult.id == subject_result_id
    ).first()

    if not subject_result:
        raise HTTPException(status_code=404, detail="Subject result not found")

    if data.subject_code is not None:
        subject_result.subject_code = data.subject_code
    if data.subject_name is not None:
        subject_result.subject_name = data.subject_name
    if data.external_marks is not None:
        subject_result.external_marks = data.external_marks
    if data.grade is not None:
        subject_result.grade = data.grade
    if data.grade_points is not None:
        subject_result.grade_points = data.grade_points
    if data.credits is not None:
        subject_result.credits = data.credits
    if data.subject_type is not None:
        subject_result.subject_type = data.subject_type

    db.commit()
    db.refresh(subject_result)

    return {
        "message": "Subject result updated successfully",
        "subject_result": {
            "id": subject_result.id,
            "result_id": subject_result.result_id,
            "subject_code": subject_result.subject_code,
            "subject_name": subject_result.subject_name,
            "external_marks": subject_result.external_marks,
            "grade": subject_result.grade,
            "grade_points": subject_result.grade_points,
            "credits": subject_result.credits,
            "subject_type": subject_result.subject_type
        }
    }
@app.delete("/subject-results/{subject_result_id}")
def delete_subject_result(
    subject_result_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    subject_result = db.query(models.SubjectResult).filter(
        models.SubjectResult.id == subject_result_id
    ).first()

    if not subject_result:
        raise HTTPException(status_code=404, detail="Subject result not found")

    db.delete(subject_result)
    db.commit()

    return {
        "message": "Subject result deleted successfully"
    }
@app.get("/dashboard/top-students")
def get_top_students(
    limit: int = 5,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    results = (
        db.query(models.Result)
        .order_by(models.Result.cgpa.desc())
        .limit(limit)
        .all()
    )

    output = []
    for result in results:
        student = db.query(models.Student).filter(models.Student.id == result.student_id).first()
        if student:
            output.append({
                "student_id": student.id,
                "name": student.name,
                "roll_number": student.roll_number,
                "branch": student.branch,
                "cgpa": result.cgpa,
                "sgpa": result.sgpa,
                "semester": result.semester
            })

    return {
        "message": "Top students fetched successfully",
        "top_students": output
    }
@app.get("/dashboard/low-attendance")
def get_low_attendance_students(
    threshold: float = 75.0,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    students = (
        db.query(models.Student)
        .filter(models.Student.attendance_percentage < threshold)
        .all()
    )

    return {
        "message": "Low attendance students fetched successfully",
        "students": [
            {
                "student_id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "branch": s.branch,
                "attendance_percentage": s.attendance_percentage
            }
            for s in students
        ]
    }
@app.get("/dashboard/fee-defaulters")
def get_fee_defaulters(
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    students = (
        db.query(models.Student)
        .filter(models.Student.pending_fee > 0)
        .all()
    )

    return {
        "message": "Fee defaulters fetched successfully",
        "students": [
            {
                "student_id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "branch": s.branch,
                "total_fee": s.total_fee,
                "paid_fee": s.paid_fee,
                "pending_fee": s.pending_fee
            }
            for s in students
        ]
    }
@app.get("/dashboard/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    total_students = db.query(models.Student).count()
    low_attendance_count = db.query(models.Student).filter(models.Student.attendance_percentage < 75).count()
    fee_defaulters_count = db.query(models.Student).filter(models.Student.pending_fee > 0).count()
    total_faculty = db.query(models.Faculty).count()

    top_result = (
        db.query(models.Result)
        .order_by(models.Result.cgpa.desc())
        .first()
    )

    top_student = None
    if top_result:
        student = db.query(models.Student).filter(models.Student.id == top_result.student_id).first()
        if student:
            top_student = {
                "student_id": student.id,
                "name": student.name,
                "roll_number": student.roll_number,
                "cgpa": top_result.cgpa
            }

    return {
        "total_students": total_students,
        "total_faculty": total_faculty,
        "low_attendance_count": low_attendance_count,
        "fee_defaulters_count": fee_defaulters_count,
        "top_student": top_student
    }
@app.get("/dashboard/subject-topper")
def get_single_subject_topper(
    subject_name: str,
    db: Session = Depends(get_db),
    user=Depends(require_hod)
):
    subject_results = db.query(models.SubjectResult).filter(
        models.SubjectResult.subject_name.ilike(f"%{subject_name}%")
    ).all()

    if not subject_results:
        raise HTTPException(status_code=404, detail="No results found for this subject")

    topper = max(subject_results, key=lambda x: x.external_marks)

    result = db.query(models.Result).filter(models.Result.id == topper.result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    student = db.query(models.Student).filter(models.Student.id == result.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "subject_name": topper.subject_name,
        "subject_code": topper.subject_code,
        "student_id": student.id,
        "student_name": student.name,
        "roll_number": student.roll_number,
        "branch": student.branch,
        "external_marks": topper.external_marks,
        "grade": topper.grade,
        "grade_points": topper.grade_points
    }