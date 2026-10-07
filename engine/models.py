from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
import re


class WebsiteType(StrEnum):
    AUTO = "AUTO"
    FULL_ECOMMERCE_STORE = "FULL_ECOMMERCE_STORE"
    BRAND_WEBSITE = "BRAND_WEBSITE"
    SERVICE_WEBSITE = "SERVICE_WEBSITE"
    LANDING_PAGE = "LANDING_PAGE"
    PRODUCT_PAGE = "PRODUCT_PAGE"
    SALES_PAGE = "SALES_PAGE"
    COLLECTION_PAGE = "COLLECTION_PAGE"
    BLOG_EDITORIAL = "BLOG_EDITORIAL"
    PORTFOLIO = "PORTFOLIO"
    WEB_APP = "WEB_APP"
    EXISTING_WEBSITE_REDESIGN = "EXISTING_WEBSITE_REDESIGN"


class Target(StrEnum):
    AUTO = "AUTO"
    CUSTOM_WEB = "CUSTOM_WEB"
    SHOPIFY = "SHOPIFY"
    WEBFLOW = "WEBFLOW"


class Stage(StrEnum):
    BRIEF = "BRIEF"
    DISCOVERY = "DISCOVERY"
    VISUAL_REVIEW = "VISUAL_REVIEW"
    DESIGN_LOCKED = "DESIGN_LOCKED"
    PRODUCTION = "PRODUCTION"
    QA = "QA"
    FINAL_REVIEW = "FINAL_REVIEW"
    READY = "READY"
    BLOCKED = "BLOCKED"


class Reference(BaseModel):
    url: HttpUrl
    role: Literal["infer", "composition", "motion", "product presentation", "navigation", "typography principle"] = "infer"

    @field_validator("url")
    @classmethod
    def no_credentials(cls, value):
        if value.username or value.password:
            raise ValueError("Reference URLs must not contain credentials")
        return value


class Content(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    text: str = Field(max_length=10000)
    permission: Literal["SUPPLIED", "APPROVED", "RESEARCH_SUPPORTED", "UNAUTHORIZED"] = "SUPPLIED"
    source: str | None = None


class Requirement(BaseModel):
    classification: Literal["REQUIRED", "LOCKED", "ALLOWED", "PREFERRED", "AVOID", "FORBIDDEN"]
    text: str = Field(min_length=1, max_length=3000)
    area: str = "general"


class Brief(BaseModel):
    brand_name: str = Field(min_length=1, max_length=100)
    website_type: WebsiteType = WebsiteType.AUTO
    target: Target = Target.AUTO
    current_url: HttpUrl | None = None
    references: list[Reference] = Field(default_factory=list, max_length=8)
    instructions: str = Field(default="", max_length=20000)
    goals: str = Field(default="", max_length=4000)
    audience: str = Field(default="", max_length=2000)
    offerings: list[str] = Field(default_factory=list, max_length=30)
    functionality: list[str] = Field(default_factory=list, max_length=30)
    palette: list[str] = Field(default_factory=list, max_length=6)
    fonts: list[str] = Field(default_factory=list, max_length=3)
    content: list[Content] = Field(default_factory=list, max_length=100)
    requirements: list[Requirement] = Field(default_factory=list, max_length=100)
    demo: bool = False

    @field_validator("current_url")
    @classmethod
    def no_site_credentials(cls, value):
        if value and (value.username or value.password):
            raise ValueError("Website URLs must not contain credentials")
        return value

    @field_validator("brand_name")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Brand name cannot be blank")
        return value.strip()

    @field_validator("palette")
    @classmethod
    def hex_colors(cls, value):
        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in value):
            raise ValueError("Palette colors must be six-digit hex colors")
        return value

    @field_validator("fonts")
    @classmethod
    def safe_font_names(cls, value):
        if any(not re.fullmatch(r"[\w ,.-]{1,100}", name) for name in value):
            raise ValueError("Invalid font family")
        return value


class Decision(BaseModel):
    id: str
    question: str
    reason: str
    dependency: str
    severity: Literal["info", "warning", "critical"]
    blocking: bool
    attempted_resolution: list[str]
    options: list[str]
    recommended_option: str
    affected_stages: list[str]
    status: Literal["OPEN", "RESOLVED"] = "OPEN"
    resolution: str | None = None


class Review(BaseModel):
    action: Literal["KEEP", "REVISE", "REJECT"]
    version: int = Field(ge=1)
    feedback: str = Field(default="", max_length=5000)
    patches: dict = Field(default_factory=dict)


class FinalApproval(BaseModel):
    build_id: str
    approved: bool = True


ROLES = {
    "Orchestrator": "State transitions, durable jobs and recovery",
    "Project Architect": "Scope, sitemap and preserved functionality",
    "Reference Analyst": "Measured evidence with provenance and confidence",
    "Researcher": "Source-backed constraints and UX principles",
    "Asset Analyst": "Exact files, hashes, metadata and usage permissions",
    "Design Strategist": "Constitution and platform-aware decisions",
    "Visual Designer": "Coherent prototypes and bounded revision patches",
    "Platform Specialist": "Native platform capabilities and blockers",
    "Developer": "Build only from an approved design snapshot",
    "Visual QA": "Rendered responsive evidence and design comparison",
    "Functional QA": "Links, controls and platform contract validation",
    "Accessibility QA": "Semantics, labels, keyboard and contrast",
    "Performance QA": "Asset weight and measured browser timings",
    "Content Integrity QA": "Authorized text and exact asset verification",
    "Release Manager": "Independent QA authority, manifests and release gates",
}
