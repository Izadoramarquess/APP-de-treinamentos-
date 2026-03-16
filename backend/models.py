from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Float, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base
from pydantic import BaseModel
from typing import List, Optional

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user") # 'admin' or 'user'
    status = Column(String, default="pending") # 'pending', 'approved', 'rejected'
    department = Column(String, nullable=True)

    enrollments = relationship("Enrollment", back_populates="user")
    certificates = relationship("Certificate", back_populates="user")
    course_progress = relationship("CourseProgress", back_populates="user")

class LearningPath(Base):
    __tablename__ = "learning_paths"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    
    courses = relationship("Course", back_populates="path", order_by="Course.order")
    enrollments = relationship("Enrollment", back_populates="path")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    path_id = Column(Integer, ForeignKey("learning_paths.id"))
    order = Column(Integer, default=1)
    title = Column(String, index=True)
    description = Column(Text)
    video_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    certificate_template_url = Column(String, nullable=True)
    validity_months = Column(Integer, nullable=True)
    
    path = relationship("LearningPath", back_populates="courses")
    materials = relationship("Material", back_populates="course")
    questions = relationship("Question", back_populates="course")
    progress = relationship("CourseProgress", back_populates="course")
    certificates = relationship("Certificate", back_populates="course")

class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    title = Column(String)
    file_url = Column(String)
    
    course = relationship("Course", back_populates="materials")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    text = Column(Text)
    option_a = Column(String)
    option_b = Column(String)
    option_c = Column(String)
    option_d = Column(String)
    correct_option = Column(String)
    is_final_exam = Column(Boolean, default=False)
    timestamp = Column(Float, nullable=True)
    
    course = relationship("Course", back_populates="questions")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    path_id = Column(Integer, ForeignKey("learning_paths.id"))
    enrolled_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="enrollments")
    path = relationship("LearningPath", back_populates="enrollments")

class CourseProgress(Base):
    __tablename__ = "course_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    is_completed = Column(Boolean, default=False)
    score_final = Column(Float, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="course_progress")
    course = relationship("Course", back_populates="progress")

class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    file_url = Column(String)
    issued_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="certificates")
    course = relationship("Course", back_populates="certificates")

# --- Pydantic Schemas ---

class MaterialSchema(BaseModel):
    id: int
    title: str
    file_url: str
    class Config: from_attributes = True

class QuestionSchema(BaseModel):
    id: int
    text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    is_final_exam: bool
    timestamp: Optional[float] = None
    class Config: from_attributes = True

class CourseSchema(BaseModel):
    id: int
    path_id: int
    order: int
    title: str
    description: str
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    certificate_template_url: Optional[str] = None
    validity_months: Optional[int] = None
    materials: List[MaterialSchema] = []
    questions: List[QuestionSchema] = []
    class Config: from_attributes = True

class LearningPathSchema(BaseModel):
    id: int
    title: str
    description: str
    courses: List[CourseSchema] = []
    class Config: from_attributes = True

class UserSchema(BaseModel):
    id: int
    username: str
    email: str
    role: str
    status: str
    department: Optional[str] = None
    class Config: from_attributes = True
