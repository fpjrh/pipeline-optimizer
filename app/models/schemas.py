from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    github_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String, unique=True, nullable=False)
    default_branch = Column(String, default="main")
    last_collected_at = Column(DateTime, nullable=True)

    workflows = relationship("Workflow", back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repository {self.full_name}>"


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    github_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    yaml_content = Column(Text, nullable=True)

    repository = relationship("Repository", back_populates="workflows")
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Workflow {self.name}>"


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    github_run_id = Column(Integer, unique=True, nullable=False)
    run_number = Column(Integer, nullable=False)
    status = Column(String, nullable=True)
    conclusion = Column(String, nullable=True)
    trigger_event = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    total_compute_cost = Column(Float, nullable=True)
    total_llm_cost = Column(Float, nullable=True)
    commit_sha = Column(String, nullable=True)
    branch = Column(String, nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    jobs = relationship("Job", back_populates="run", cascade="all, delete-orphan")
    llm_calls = relationship("LLMCall", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_workflow_runs_started_at", "started_at"),
    )

    def __repr__(self):
        return f"<WorkflowRun #{self.run_number}>"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    github_job_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    runner_os = Column(String, nullable=True)
    runner_type = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    conclusion = Column(String, nullable=True)
    depends_on = Column(Text, nullable=True)  # JSON list of job names

    run = relationship("WorkflowRun", back_populates="jobs")
    steps = relationship("Step", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job {self.name}>"


class Step(Base):
    __tablename__ = "steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    name = Column(String, nullable=False)
    number = Column(Integer, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    conclusion = Column(String, nullable=True)

    job = relationship("Job", back_populates="steps")

    def __repr__(self):
        return f"<Step {self.name}>"


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)
    job_name = Column(String, nullable=True)
    step_name = Column(String, nullable=True)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    purpose = Column(String, nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    repo_full_name = Column(String, nullable=True)
    commit_sha = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    workflow_name = Column(String, nullable=True)
    github_run_id = Column(Integer, nullable=True)

    run = relationship("WorkflowRun", back_populates="llm_calls")

    __table_args__ = (
        Index("ix_llm_calls_timestamp", "timestamp"),
        Index("ix_llm_calls_provider_model", "provider", "model"),
    )

    def __repr__(self):
        return f"<LLMCall {self.provider}/{self.model}>"


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    estimated_savings = Column(String, nullable=True)
    priority = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="new")
    created_at = Column(DateTime, nullable=False)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=True)

    __table_args__ = (
        Index("ix_recommendations_status", "status"),
    )

    def __repr__(self):
        return f"<Recommendation {self.title}>"
