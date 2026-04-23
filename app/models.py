from sqlalchemy import Column, Integer, String, Float, ForeignKey,Text
from sqlalchemy.orm import relationship
from app.database import Base
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    roll_number = Column(String(50), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    branch = Column(String(100), nullable=True)
    role = Column(String(50), nullable=False, default="student")

    attendance_percentage = Column(Float, nullable=True, default=0)
    total_fee = Column(Float, nullable=True, default=0)
    paid_fee = Column(Float, nullable=True, default=0)
    pending_fee = Column(Float, nullable=True, default=0)

    results = relationship("Result", back_populates="student", cascade="all, delete")


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    semester = Column(String(100), nullable=False)
    exam_month = Column(String(50), nullable=True)
    exam_year = Column(Integer, nullable=True)
    sgpa = Column(Float, nullable=True)
    cgpa = Column(Float, nullable=True)

    student = relationship("Student", back_populates="results")
    subjects = relationship("SubjectResult", back_populates="result", cascade="all, delete")


class SubjectResult(Base):
    __tablename__ = "subject_results"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("results.id"), nullable=False)

    subject_code = Column(String(50), nullable=False)
    subject_name = Column(String(200), nullable=False)
    external_marks = Column(Integer, nullable=True)
    grade = Column(String(10), nullable=True)
    grade_points = Column(Integer, nullable=True)
    credits = Column(Integer, nullable=True)
    subject_type = Column(String(50), nullable=True)   # theory / lab / internship

    result = relationship("Result", back_populates="subjects")
class Faculty(Base):
    __tablename__ = "faculty"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    department = Column(String(100), nullable=True)
    subject = Column(String(200), nullable=True)
    designation = Column(String(100), nullable=True)
    room_number = Column(String(50), nullable=True)
    status = Column(String(100), nullable=True, default="Available")
    availability_note = Column(String(200), nullable=True)
class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id = Column(Integer, primary_key=True, index=True)
    subject_name = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    document_type = Column(String(100), nullable=False)   # notes / previous_paper / lab_manual / syllabus
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_by = Column(String(100), nullable=True)
class SyllabusDocument(Base):
    __tablename__ = "syllabus_documents"

    id = Column(Integer, primary_key=True, index=True)
    subject_name = Column(String(200), nullable=False)
    title = Column(String(200), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    uploaded_by = Column(String(100), nullable=True)
