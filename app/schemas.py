from pydantic import BaseModel, EmailStr
from typing import List, Optional


class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    roll_number: str
    password: str
    branch: Optional[str] = None
    role: Optional[str] = "student"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SubjectResultCreate(BaseModel):
    subject_code: str
    subject_name: str
    external_marks: Optional[int] = None
    grade: Optional[str] = None
    grade_points: Optional[int] = None
    credits: Optional[int] = None
    subject_type: Optional[str] = None


class ResultCreate(BaseModel):
    student_id: int
    semester: str
    exam_month: Optional[str] = None
    exam_year: Optional[int] = None
    sgpa: Optional[float] = None
    cgpa: Optional[float] = None
    subjects: List[SubjectResultCreate]


class SubjectResultResponse(BaseModel):
    subject_code: str
    subject_name: str
    external_marks: Optional[int]
    grade: Optional[str]
    grade_points: Optional[int]
    credits: Optional[int]
    subject_type: Optional[str]

    class Config:
        from_attributes = True


class ResultResponse(BaseModel):
    id: int
    semester: str
    exam_month: Optional[str]
    exam_year: Optional[int]
    sgpa: Optional[float]
    cgpa: Optional[float]
    subjects: List[SubjectResultResponse]

    class Config:
        from_attributes = True
class ChatQuery(BaseModel):
    message: str
class AttendanceUpdate(BaseModel):
    attendance_percentage: float


class FeesUpdate(BaseModel):
    total_fee: float
    paid_fee: float
class FacultyCreate(BaseModel):
    name: str
    email: str | None = None
    department: str | None = None
    subject: str | None = None
    designation: str | None = None
    room_number: str | None = None
    status: str | None = "Available"
    availability_note: str | None = None


class FacultyStatusUpdate(BaseModel):
    status: str
    availability_note: str | None = None
    room_number: str | None = None
class StudyMaterialResponse(BaseModel):
    id: int
    subject_name: str
    title: str
    document_type: str
    file_name: str
    file_path: str
    uploaded_by: str | None = None

    class Config:
        from_attributes = True
class SyllabusQuestion(BaseModel):
    subject_name: str
    question: str
class StudentUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    roll_number: str | None = None
    branch: str | None = None
    role: str | None = None
class ResultUpdate(BaseModel):
    semester: str | None = None
    exam_month: str | None = None
    exam_year: int | None = None
    sgpa: float | None = None
    cgpa: float | None = None
from typing import Optional
from pydantic import BaseModel

class SubjectResultUpdate(BaseModel):
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    external_marks: Optional[int] = None
    grade: Optional[str] = None
    grade_points: Optional[float] = None
    credits: Optional[float] = None
    subject_type: Optional[str] = None