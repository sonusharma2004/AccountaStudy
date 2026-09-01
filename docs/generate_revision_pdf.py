"""
AccountaStudy — Revision & Viva Prep PDF Generator
Builds a thorough study guide covering the full stack of the project plus 40+
viva Q&A with detailed answers, formatted for easy reading.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, Image,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "revision-and-viva.pdf")

# ---------- Colour palette ----------
PRIMARY = colors.HexColor("#1E40AF")
ACCENT = colors.HexColor("#3B82F6")
DARK = colors.HexColor("#0F172A")
TEXT = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#64748B")
LIGHT = colors.HexColor("#F1F5F9")
SUCCESS = colors.HexColor("#16A34A")
WARN = colors.HexColor("#D97706")
DANGER = colors.HexColor("#DC2626")
CARD_BG = colors.HexColor("#F8FAFC")
BORDER = colors.HexColor("#E2E8F0")

# ---------- Styles ----------
styles = getSampleStyleSheet()

H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=22, leading=28, textColor=PRIMARY, spaceBefore=10, spaceAfter=14,
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=15, leading=20, textColor=DARK, spaceBefore=14, spaceAfter=8,
)
H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
    fontSize=12.5, leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=4,
)
BODY = ParagraphStyle(
    "Body", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=10.5, leading=15, textColor=TEXT, spaceAfter=6, alignment=TA_JUSTIFY,
)
BULLET = ParagraphStyle(
    "Bullet", parent=BODY, leftIndent=14, bulletIndent=2,
    spaceAfter=3, leading=14,
)
SMALL = ParagraphStyle(
    "Small", parent=BODY, fontSize=9.5, leading=13, textColor=MUTED,
)
CODE = ParagraphStyle(
    "Code", parent=BODY, fontName="Courier", fontSize=9, leading=12,
    textColor=DARK, backColor=LIGHT, leftIndent=8, rightIndent=8,
    spaceBefore=4, spaceAfter=6, borderPadding=6,
)
Q = ParagraphStyle(
    "Q", parent=BODY, fontName="Helvetica-Bold", fontSize=11, leading=15,
    textColor=PRIMARY, spaceBefore=12, spaceAfter=4,
)
A = ParagraphStyle(
    "A", parent=BODY, fontSize=10.3, leading=14.5, spaceAfter=8,
)
NOTE = ParagraphStyle(
    "Note", parent=BODY, fontSize=10, leading=14,
    textColor=DARK, backColor=colors.HexColor("#FEF9C3"),
    leftIndent=8, rightIndent=8, borderPadding=6, spaceBefore=4, spaceAfter=8,
)


# ---------- Page decoration ----------
def on_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    # Header strip
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, height - 1.1 * cm, width, 1.1 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(1.5 * cm, height - 0.7 * cm, "AccountaStudy — Revision & Viva Guide")
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(width - 1.5 * cm, height - 0.7 * cm, "Sonu Sharma · Medicaps University")
    # Footer
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(1.5 * cm, 0.8 * cm, "github.com/sonusharma2004/AccountaStudy")
    canvas.drawRightString(width - 1.5 * cm, 0.8 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.line(1.5 * cm, 1.1 * cm, width - 1.5 * cm, 1.1 * cm)
    canvas.restoreState()


# ---------- Helpers ----------
def section_box(title, color=PRIMARY):
    tbl = Table([[title]], colWidths=[17.0 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 13),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return tbl


def kv_table(rows, col_widths=(5.0 * cm, 12.0 * cm), header=None):
    data = []
    if header:
        data.append(header)
    data.extend(rows)
    t = Table(data, colWidths=list(col_widths), hAlign="LEFT", repeatRows=1 if header else 0)
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("BACKGROUND", (0, 0), (0, -1), CARD_BG),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), DARK),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


def bullet_list(items, style=BULLET):
    return [Paragraph(f"• {it}", style) for it in items]


def code_block(text):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = safe.replace("\n", "<br/>")
    return Paragraph(safe, CODE)


# ─────────────────────────────────────────────
# CONTENT
# ─────────────────────────────────────────────
story = []

# ───── Cover ─────
story += [
    Spacer(1, 3.5 * cm),
    Paragraph("AccountaStudy", ParagraphStyle(
        "Cover", parent=H1, fontSize=42, leading=46,
        textColor=PRIMARY, alignment=TA_CENTER, spaceAfter=12,
    )),
    Paragraph("Complete Revision &amp; Viva Preparation Guide",
              ParagraphStyle("CoverSub", parent=H2, fontSize=17,
                             alignment=TA_CENTER, textColor=DARK, spaceAfter=24)),
    Paragraph("From Basics to Advanced — Tech Stack, Architecture, Flow, Working &amp; 50+ Viva Q&amp;A",
              ParagraphStyle("CoverDesc", parent=BODY, fontSize=12,
                             alignment=TA_CENTER, textColor=MUTED, spaceAfter=40)),
]

cover_meta = Table([
    ["Project", "AccountaStudy — Student Accountability System"],
    ["Type", "Full-Stack MERN-style Web Application (MongoDB · Express · Vanilla JS · Node)"],
    ["Developer", "Sonu Sharma — Computer Science & Engineering"],
    ["Institution", "Medicaps University, Indore"],
    ["Guides", "Prof. Amrata Gupta · Prof. Laxmi Kag"],
    ["HOD", "Prof. (Dr.) Kailash Chandra Bandhu"],
    ["Live URL", "darling-bienenstitch-be5932.netlify.app"],
    ["Repository", "github.com/sonusharma2004/AccountaStudy"],
], colWidths=[3.6 * cm, 12.6 * cm])
cover_meta.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("BACKGROUND", (0, 0), (0, -1), PRIMARY),
    ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("BACKGROUND", (1, 0), (1, -1), LIGHT),
    ("TEXTCOLOR", (1, 0), (1, -1), DARK),
    ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ("TOPPADDING", (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))
story += [cover_meta, Spacer(1, 2 * cm)]
story += [Paragraph(
    "This document is your one-stop revision guide. It covers what the project does, every library used, how data flows from a button click to the database and back, and 50+ likely viva questions with detailed answers. Read sections in order or jump to the viva section to drill.",
    ParagraphStyle("CoverHint", parent=BODY, alignment=TA_CENTER,
                   fontSize=10, textColor=MUTED))]
story.append(PageBreak())


# ───── Table of Contents ─────
story.append(Paragraph("Table of Contents", H1))
toc_data = [
    ["1.", "Project Overview & Problem It Solves"],
    ["2.", "Technology Stack — Frontend, Backend, Database, Tooling"],
    ["3.", "Every Library Used (with version & purpose)"],
    ["4.", "Project Folder Structure"],
    ["5.", "Database Schema (User · Submission · Session)"],
    ["6.", "Complete REST API Reference"],
    ["7.", "End-to-End Project Flow (User Journey)"],
    ["8.", "Authentication & Security Flow (JWT + bcrypt)"],
    ["9.", "Daily Submission Lifecycle (with screenshots)"],
    ["10.", "Study Timer & Session Tracking Working"],
    ["11.", "Leaderboard & Points System Working"],
    ["12.", "Admin Verification Working"],
    ["13.", "Deployment Architecture (Render + Netlify + MongoDB Atlas)"],
    ["14.", "Quick Local Setup / Run Commands"],
    ["15.", "Key Code Snippets to Remember"],
    ["16.", "Viva Questions — Basic (Q1–Q15)"],
    ["17.", "Viva Questions — Intermediate (Q16–Q35)"],
    ["18.", "Viva Questions — Advanced & Tricky (Q36–Q55)"],
    ["19.", "Quick Revision Cheat-Sheet"],
]
toc_tbl = Table(toc_data, colWidths=[1.2 * cm, 15.5 * cm])
toc_tbl.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 11),
    ("TOPPADDING", (0, 0), (-1, -1), 6),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("TEXTCOLOR", (1, 0), (1, -1), DARK),
]))
story += [toc_tbl, PageBreak()]


# ─── 1. Overview ───
story.append(section_box("1. Project Overview & Problem It Solves"))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "<b>AccountaStudy</b> is a student accountability web application that enforces daily study consistency through verifiable proof. "
    "Students must submit two screenshots every day — one of their study timer and one of the questions they solved. "
    "An admin reviews each submission and assigns a status (<i>Completed / Half Day / Leave / Fine</i>), which drives the student's streak, points, and leaderboard rank.",
    BODY))
story.append(Paragraph("Why it matters", H3))
story += bullet_list([
    "<b>Real proof, not self-reporting</b> — students can't fake study hours; screenshots are timestamp evidence.",
    "<b>Gamification</b> — streaks, points, rankings and rank badges create healthy peer pressure.",
    "<b>Admin oversight</b> — a teacher or peer admin verifies every submission, ensuring quality and honesty.",
    "<b>Flexible attendance</b> — students get 3 leaves and 3 half-days per term; system auto-deducts and shows remaining quota.",
    "<b>Built-in timer</b> — a focused Library Mode helps avoid distractions during study sessions.",
])
story.append(Paragraph("Problem statement", H3))
story.append(Paragraph(
    "Most study-tracking apps rely on self-reported hours, which students inflate. AccountaStudy fixes this by combining "
    "screenshot-based daily proof, admin verification, streaks, and a public leaderboard — so consistency becomes "
    "measurable, social, and competitive.", BODY))
story.append(PageBreak())


# ─── 2. Tech Stack ───
story.append(section_box("2. Technology Stack"))
story.append(Spacer(1, 8))
story.append(Paragraph("The application follows a classic 3-tier client–server architecture:", BODY))

story.append(Paragraph("Frontend (Presentation Layer)", H3))
story.append(kv_table([
    ["HTML5", "Markup for the single-page UI (index.html, ~650 lines)"],
    ["CSS3", "Custom styling, CSS variables, flex/grid layouts, focus-mode classes (style.css)"],
    ["Vanilla JavaScript (ES2022)", "All app logic, fetch() calls, DOM manipulation, state object S (app.js, ~1300 lines)"],
    ["Chart.js 4.4.1", "Bar charts, doughnut/line charts on Dashboard & Analytics (loaded via CDN)"],
    ["Google Fonts", "Plus Jakarta Sans (body) + Fraunces (display headings)"],
], header=["Tool", "Role in Project"]))

story.append(Paragraph("Backend (Application Layer)", H3))
story.append(kv_table([
    ["Node.js 18 LTS", "JavaScript runtime that executes the server"],
    ["Express.js 4.19", "Web framework — routing, middleware pipeline, request/response handling"],
    ["Mongoose 8.4", "ODM (Object Data Modelling) layer for MongoDB — schemas, validation, queries"],
    ["JSON Web Tokens 9.0", "Stateless authentication — signs and verifies tokens"],
    ["bcryptjs 2.4", "One-way password hashing with salt (cost factor 12)"],
    ["Multer 1.4", "Middleware for handling multipart/form-data (file uploads)"],
    ["CORS 2.8", "Allow the frontend domain to call the backend across origins"],
    ["dotenv 16.4", "Load environment variables from .env file"],
    ["Morgan 1.10", "HTTP request logger (only in development)"],
    ["Nodemon 3.1 (dev)", "Auto-restarts the server on code changes during development"],
], header=["Tool", "Role in Project"]))

story.append(Paragraph("Database (Data Layer)", H3))
story.append(kv_table([
    ["MongoDB 6.x", "NoSQL document database storing users, submissions, sessions"],
    ["MongoDB Atlas", "Cloud-hosted managed MongoDB cluster (free M0 tier)"],
], header=["Tool", "Role"]))

story.append(Paragraph("Hosting & DevOps", H3))
story.append(kv_table([
    ["Render.com", "Backend host — auto-deploys on every git push to main"],
    ["Netlify", "Frontend static host — CDN-served HTML/CSS/JS"],
    ["GitHub", "Source control + CI/CD trigger for Render"],
    ["VS Code", "IDE used for development"],
    ["Netlify CLI", "Production deploys via terminal (netlify deploy --prod)"],
], header=["Tool", "Role"]))
story.append(PageBreak())


# ─── 3. Every Library ───
story.append(section_box("3. Every Library Used — In Detail"))
story.append(Spacer(1, 8))

lib_data = [
    ["express", "4.19.2", "Backend framework. Provides app.use(), Router(), middleware chain, req/res objects, JSON parsing."],
    ["mongoose", "8.4.1", "MongoDB ODM. Defines Schemas, automatic validation, pre-save hooks, populate(), aggregation."],
    ["bcryptjs", "2.4.3", "Pure-JS bcrypt implementation. Used in User.pre('save') hook to hash passwords with salt of cost 12."],
    ["jsonwebtoken", "9.0.2", "Issues JWTs on login/register; verifies them in protect() middleware. Stateless auth."],
    ["multer", "1.4.5-lts.1", "Multipart parser. Configured with diskStorage to save screenshots to /uploads/timer and /uploads/questions, 10MB limit, image-only fileFilter."],
    ["cors", "2.8.5", "Adds Access-Control-Allow-* headers. Whitelisted: localhost:5500, .netlify.app, .onrender.com."],
    ["dotenv", "16.4.5", "Reads .env at startup — loads MONGODB_URI, JWT_SECRET, JWT_EXPIRES_IN, PORT, NODE_ENV."],
    ["morgan", "1.10.0", "HTTP request logger middleware — only active when NODE_ENV=development."],
    ["nodemon", "3.1.4", "Dev-only. Watches files and restarts node server.js automatically on save."],
    ["chart.js", "4.4.1", "Frontend charting library used for the 7-day study chart, subject doughnut, weekly bars (loaded via CDN)."],
]
story.append(kv_table(lib_data,
                     col_widths=(2.6 * cm, 1.7 * cm, 12.7 * cm),
                     header=["Package", "Version", "What it does in this project"]))
story.append(Spacer(1, 10))
story.append(Paragraph("Why this stack?", H3))
story += bullet_list([
    "<b>JavaScript everywhere</b> — same language frontend and backend reduces context-switching.",
    "<b>Express + Mongoose</b> — minimal boilerplate, schema-based validation, fast prototyping.",
    "<b>JWT</b> — stateless, scales horizontally, no session store needed.",
    "<b>Multer</b> — battle-tested for multipart uploads, plays well with Express.",
    "<b>MongoDB</b> — schema-flexible, perfect for documents like submissions whose shape evolves.",
    "<b>Vanilla JS frontend</b> — no React build pipeline; loads instantly, easy to host on any CDN, ideal for a college project.",
])
story.append(PageBreak())


# ─── 4. Folder Structure ───
story.append(section_box("4. Project Folder Structure"))
story.append(Spacer(1, 8))
tree = """AccountaStudy/
├── backend/
│   ├── server.js              # Express entry point
│   ├── package.json           # Dependencies + scripts
│   ├── .env                   # Secrets (not committed)
│   ├── config/
│   │   ├── db.js              # mongoose.connect()
│   │   └── multer.js          # File-upload config
│   ├── middleware/
│   │   ├── auth.js            # protect(), adminOnly(), generateToken()
│   │   └── errorHandler.js    # Centralised error responses
│   ├── models/
│   │   ├── User.js            # User schema + pre-save bcrypt hook
│   │   ├── Submission.js      # Daily proof schema + STATUS_POINTS
│   │   └── Session.js         # Timer-session schema
│   ├── controllers/
│   │   ├── authController.js  # register / login / getMe
│   │   ├── submissionController.js  # upload / verify / my / today
│   │   ├── sessionController.js     # start / stop / user
│   │   ├── leaderboardController.js # daily / weekly / overall ranks
│   │   └── adminController.js       # users / stats / analytics
│   ├── routes/
│   │   ├── auth.js
│   │   ├── submission.js
│   │   ├── session.js
│   │   ├── leaderboard.js
│   │   └── admin.js
│   ├── scripts/
│   │   └── seed.js            # Populates demo data
│   └── uploads/               # Saved screenshots (timer/, questions/)
│
├── frontend/
│   ├── index.html             # All UI markup (auth + app shell)
│   ├── style.css              # Theme, layout, focus-mode styles
│   └── app.js                 # Logic — fetch(), state S, render functions
│
├── docs/
│   ├── project-report.pdf     # Formal report with screenshots
│   ├── presentation-guide.pdf # Step-by-step demo flow
│   ├── revision-and-viva.pdf  # THIS FILE
│   └── screenshots/           # PNGs of each app screen
│
├── README.md                  # Project intro + setup + features
└── .gitignore"""
story.append(code_block(tree))
story.append(PageBreak())


# ─── 5. Database Schema ───
story.append(section_box("5. Database Schema"))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "Three Mongoose collections power the system. Every schema has <b>timestamps: true</b> (auto createdAt + updatedAt).",
    BODY))

story.append(Paragraph("5.1 User", H3))
story.append(kv_table([
    ["name", "String, required, 2–50 chars"],
    ["email", "String, required, unique, lowercase, regex-validated"],
    ["password", "String, required, min 6, select:false (never returned in queries)"],
    ["role", "Enum [student, admin], default 'student'"],
    ["studentType", "Enum [intern, fulltime], default 'fulltime'"],
    ["totalStudyHours", "Number, default 0 — incremented on session stop / submission"],
    ["streak", "Number, default 0 — consecutive completed/halfday days"],
    ["longestStreak", "Number, default 0 — high watermark"],
    ["lastStudyDate", "Date — used to detect missed days"],
    ["totalCompleted / totalHalfDay / totalLeave / totalFines", "Counters for status types"],
    ["points", "Number — running total awarded by submission verifications"],
    ["leavesRemaining", "Number, default 3 — quota counter"],
    ["halfDaysRemaining", "Number, default 3 — quota counter"],
    ["avatar / isActive", "Profile flags"],
], header=["Field", "Meaning / Constraints"]))
story.append(Paragraph(
    "<b>Hooks:</b> pre('save') hashes the password with bcrypt (12 salt rounds) if modified. <b>Methods:</b> comparePassword(), getInitials(). <b>Virtuals:</b> submissions (one-to-many via userId).",
    SMALL))

story.append(Paragraph("5.2 Submission", H3))
story.append(kv_table([
    ["userId", "ObjectId ref → User, indexed"],
    ["date", "String 'YYYY-MM-DD', indexed — easy daily lookup"],
    ["subject", "Enum 9 subjects (Mathematics, Physics, … Other)"],
    ["hoursStudied", "Number 0.5–24"],
    ["notes", "String, max 500"],
    ["timerScreenshot / questionScreenshot", "Relative path: timer/<file>.jpg or leave/placeholder.jpg"],
    ["status", "Enum [pending, completed, halfday, leave, fine], default 'pending'"],
    ["adminNotes", "String, max 300 — feedback from admin"],
    ["verifiedBy / verifiedAt / isVerified", "Audit trail of admin action"],
    ["pointsAwarded", "Auto-set by pre-save hook based on status"],
], header=["Field", "Meaning"]))
story.append(Paragraph(
    "<b>Compound unique index:</b> { userId: 1, date: 1 } — guarantees one submission per student per day. "
    "<b>Pre-save hook:</b> when status changes, sets pointsAwarded from STATUS_POINTS map "
    "({completed:100, halfday:40, leave:0, fine:-20}) and flips isVerified to true.",
    SMALL))

story.append(Paragraph("5.3 Session", H3))
story.append(kv_table([
    ["userId", "ObjectId ref → User"],
    ["subject", "Same 9-subject enum"],
    ["startTime / endTime", "Date objects"],
    ["duration", "Number in seconds"],
    ["isActive", "Boolean — true while timer runs"],
    ["date", "String 'YYYY-MM-DD' — auto-set from startTime"],
], header=["Field", "Meaning"]))
story.append(Paragraph(
    "<b>Pre-save:</b> if endTime is set, computes duration = (endTime − startTime) / 1000. "
    "Auto-cleanup: startSession finds any isActive:true session for the user and silently closes it to prevent duplicates.",
    SMALL))
story.append(PageBreak())


# ─── 6. API ───
story.append(section_box("6. REST API Reference"))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "Base URL (production): <font color='#1E40AF'><b>https://accountastudy.onrender.com/api</b></font>. "
    "All protected routes require <b>Authorization: Bearer &lt;JWT&gt;</b>.", BODY))

api_rows = [
    ["POST", "/api/auth/register", "Public", "Create student account (name, email, password, studentType)"],
    ["POST", "/api/auth/login", "Public", "Authenticate & return JWT + user"],
    ["GET", "/api/auth/me", "Private", "Get fresh profile of logged-in user"],
    ["PUT", "/api/auth/update-profile", "Private", "Edit profile (name)"],
    ["POST", "/api/submission/upload", "Student", "Submit daily proof (multipart: 2 screenshots)"],
    ["POST", "/api/submission", "Student", "Alias for upload"],
    ["GET", "/api/submission/my", "Student", "Personal submission history"],
    ["GET", "/api/submission/today-status", "Private", "Has the student submitted today?"],
    ["GET", "/api/submission/all", "Admin", "All submissions with filters (status, date)"],
    ["POST", "/api/submission/verify", "Admin", "Set status + admin notes on a submission"],
    ["POST", "/api/session/start", "Private", "Begin timer for a subject"],
    ["POST", "/api/session/stop", "Private", "End active session, save duration"],
    ["GET", "/api/session/user", "Private", "User's recent sessions + today's total"],
    ["GET", "/api/leaderboard?mode=", "Private", "daily | weekly | overall ranks"],
    ["GET", "/api/admin/users", "Admin", "All students with stats + today status"],
    ["DELETE", "/api/admin/user/:id", "Admin", "Delete user + their data"],
    ["PUT", "/api/admin/user/:id/toggle", "Admin", "Activate / deactivate account"],
    ["GET", "/api/admin/stats", "Admin", "System-wide counters + today breakdown"],
    ["GET", "/api/admin/analytics?days=", "Admin", "Daily-status trend over N days"],
    ["GET", "/api/health", "Public", "Health check (used by Render / monitoring)"],
]
api_tbl = Table([["Method", "Endpoint", "Access", "Purpose"]] + api_rows,
                colWidths=[1.6 * cm, 5.6 * cm, 1.7 * cm, 8.1 * cm])
api_tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD_BG]),
    ("TEXTCOLOR", (0, 1), (0, -1), ACCENT),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
]))
story.append(api_tbl)
story.append(PageBreak())


# ─── 7. End-to-End Flow ───
story.append(section_box("7. End-to-End Project Flow"))
story.append(Spacer(1, 8))
story.append(Paragraph("A student's full journey from signup to today's verified submission:", BODY))

flow_steps = [
    ("1. Register",
     "Student visits the Netlify URL → fills name, email, password, picks Intern / Full-time Aspirant. Frontend POSTs /api/auth/register. Backend validates, bcrypt-hashes password (cost 12), saves to MongoDB Atlas, signs a JWT and returns user object."),
    ("2. Login",
     "Student signs in → POST /api/auth/login. Backend finds user by email, compares password (bcrypt.compare), issues a JWT (7-day expiry by default), returns user + token. Token is stored in localStorage."),
    ("3. Load Dashboard",
     "On login, app.js calls /auth/me, /submission/my (or /all for admin), /session/user, /leaderboard in parallel. Dashboard renders Today's Study, Streak, Rank, Status, plus leave/halfday quota."),
    ("4. Start Study Timer",
     "Student clicks Study Timer → picks subject → Start. Frontend POSTs /api/session/start. Backend closes any orphaned active session, creates a new Session document (isActive:true). Frontend enters Library Focus Mode (dimmed background + side panels collapse)."),
    ("5. Stop Timer",
     "On Stop, POST /api/session/stop. Backend sets endTime, computes duration in seconds, marks isActive:false, increments user's totalStudyHours."),
    ("6. Submit Daily Proof (6 PM – 7:30 PM window)",
     "Student opens Submit Daily Proof, picks Full Day / Half Day / Leave. For Full/Half they attach timer + question screenshots. Frontend builds multipart FormData → POST /api/submission/upload. Multer saves both files under uploads/timer and uploads/questions with userId_date_timestamp.jpg filenames. Submission document is created with status='pending'."),
    ("7. Admin Verifies",
     "Admin logs in, opens Verify Submissions. Frontend GET /submission/all?limit=200. Admin clicks a card → modal opens with full screenshots + notes → picks Completed / Half Day / Leave / Fine → POST /submission/verify. Backend updates submission status, pointsAwarded, isVerified, verifiedAt; then updates student's streak, points, totalCompleted/etc."),
    ("8. Leaderboard Refreshes",
     "On the Leaderboard page, GET /api/leaderboard?mode=weekly returns aggregated rankings. Frontend animates rank bars, highlights the current user row."),
]
for title, desc in flow_steps:
    story.append(Paragraph(f"<font color='#1E40AF'><b>{title}</b></font>", H3))
    story.append(Paragraph(desc, BODY))

story.append(PageBreak())


# ─── 8. Auth Flow ───
story.append(section_box("8. Authentication & Security Flow"))
story.append(Spacer(1, 8))
story.append(Paragraph("Registration / Login", H3))
story.append(Paragraph(
    "Passwords are never stored in plain text. The User schema's <b>pre('save') hook</b> hashes them with bcrypt:",
    BODY))
story.append(code_block(
    "userSchema.pre('save', async function (next) {\n"
    "  if (!this.isModified('password')) return next();\n"
    "  const salt = await bcrypt.genSalt(12);\n"
    "  this.password = await bcrypt.hash(this.password, salt);\n"
    "  next();\n"
    "});"))
story.append(Paragraph(
    "On successful login the server signs a JWT containing the user's id:",
    BODY))
story.append(code_block(
    "jwt.sign({ id: userId }, process.env.JWT_SECRET, { expiresIn: '7d' });"))

story.append(Paragraph("Protected Routes", H3))
story.append(Paragraph(
    "Every protected endpoint runs through the <b>protect</b> middleware which:", BODY))
story += bullet_list([
    "Reads the Authorization header → extracts the token after 'Bearer '.",
    "Calls jwt.verify(token, JWT_SECRET) — throws if expired or tampered.",
    "Loads the matching user with User.findById(decoded.id).select('-password').",
    "Rejects deactivated accounts (isActive === false) with HTTP 403.",
    "Attaches user to req.user so downstream controllers can use it.",
])
story.append(Paragraph(
    "Admin-only endpoints additionally pass through <b>adminOnly</b>, which 403s any non-admin request.",
    BODY))

story.append(Paragraph("Security highlights", H3))
story += bullet_list([
    "Passwords hashed with bcrypt cost 12 (~250ms per check — slow enough to deter brute force).",
    "Password field is select:false, never returned by accident.",
    "Stateless JWT — server doesn't store sessions, scales horizontally.",
    "CORS whitelists only the production Netlify domain and Render subdomains.",
    "Multer fileFilter blocks anything that isn't jpeg/jpg/png/gif/webp; 10MB file-size cap.",
    "Mongoose enum + match validators prevent garbage values reaching the DB.",
    "Centralised errorHandler converts CastError, ValidationError, duplicate-key errors into clean JSON responses.",
])
story.append(PageBreak())


# ─── 9. Daily Submission Lifecycle ───
story.append(section_box("9. Daily Submission Lifecycle"))
story.append(Spacer(1, 8))

life = [
    ("Frontend builds FormData",
     "FormData appends: subject, hoursStudied, notes, submissionType (full|halfday|leave), and (for non-leave) the two image Blobs from <input type='file'>."),
    ("Multer parses request",
     "uploadScreenshots = upload.fields([{name:'timerScreenshot'}, {name:'questionScreenshot'}]) saves each file to its folder with name '<userId>_<date>_<timestamp>.<ext>'."),
    ("Controller validates",
     "submissionController.uploadSubmission checks: already-verified? (409), screenshots present for non-leave (400), leave/halfday allowance > 0 (400), subject + hours present (400)."),
    ("Persists submission",
     "If an existing pending submission exists, it's updated. Otherwise a new Submission document is created with status='pending'."),
    ("Updates user counters",
     "User.findByIdAndUpdate $inc totalStudyHours. For leave $inc leavesRemaining: -1; for halfday $inc halfDaysRemaining: -1 (only on new, not on edits)."),
    ("Response",
     "JSON returned with full /uploads URLs so the UI can display the saved screenshots immediately."),
    ("Admin verifies",
     "verifySubmission updates status + adminNotes, triggers pre-save hook that awards points, then increments user's streak/totalCompleted/totalFines accordingly. Streak resets on 'fine'."),
]
for t, d in life:
    story.append(Paragraph(f"<font color='#1E40AF'><b>{t}</b></font>", H3))
    story.append(Paragraph(d, BODY))

story.append(Paragraph("Points table", H3))
pts = [["completed", "+100", "Streak +1, totalCompleted +1"],
       ["halfday", "+40", "Streak +1, totalHalfDay +1"],
       ["leave", "0", "Streak unchanged, totalLeave +1"],
       ["fine", "-20", "Streak reset to 0, totalFines +1"]]
story.append(kv_table(pts, col_widths=(3.0 * cm, 2.0 * cm, 12.0 * cm),
                     header=["Status", "Points", "Effect"]))
story.append(PageBreak())


# ─── 10. Timer Flow ───
story.append(section_box("10. Study Timer & Session Tracking"))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "The timer is a focus tool — when started, the UI enters <b>Library Focus Mode</b> (dimmed warm background, "
    "side navigation collapsed, ambient styling).", BODY))
story += bullet_list([
    "<b>Start:</b> POST /api/session/start with subject. Backend auto-closes any orphaned isActive session for the user (silent), then creates a new Session.",
    "<b>Live elapsed time:</b> stored in S.timerStart on the client; setInterval updates the displayed timer every second without round-tripping.",
    "<b>Stop:</b> POST /api/session/stop. Backend sets endTime, computes duration, increments user's totalStudyHours, returns formatted duration.",
    "<b>Today's Study card</b> on dashboard sums all today's session durations (excluding active) to show real minutes — not 0m once you've studied ≥ 1 minute.",
    "<b>Get sessions:</b> GET /api/session/user returns the active session (if any), today's summary, and last N sessions.",
])
story.append(PageBreak())


# ─── 11. Leaderboard ───
story.append(section_box("11. Leaderboard & Points System"))
story.append(Spacer(1, 8))
story.append(Paragraph(
    "Three modes are computed differently based on the time scale.", BODY))
story.append(Paragraph("Daily / Weekly mode", H3))
story.append(Paragraph(
    "Uses MongoDB <b>aggregation pipeline</b> on the Submissions collection — matches submissions inside the date range with status ∈ {completed, halfday}, "
    "$group by userId summing hoursStudied + pointsAwarded, then $sort by totalHours desc. Final names/avatars come from a "
    "User.find({_id:{$in:userIds}}) followed by an in-memory map.", BODY))
story.append(Paragraph("Overall mode", H3))
story.append(Paragraph(
    "Skips aggregation — simply queries all active students and sorts by totalStudyHours desc, then by points.", BODY))
story.append(Paragraph("Rendering on frontend", H3))
story += bullet_list([
    "Top 3 get gold / silver / bronze rank badges.",
    "Current user's row is highlighted with primary-tinted background.",
    "Rank bars animate from 0 → totalHours when the page is first shown.",
    "Dashboard rank card uses the leaderboard data to find logged-in user's index + 1.",
])
story.append(PageBreak())


# ─── 12. Admin verify ───
story.append(section_box("12. Admin Verification Working"))
story.append(Spacer(1, 8))
story.append(Paragraph("UI", H3))
story += bullet_list([
    "Submissions Grid shows one card per submission: avatar, student name, date, status badge, subject pill, hours pill, two screenshot tiles, notes, Verify button.",
    "Leave submissions render a clean 🏖️ Leave Request banner instead of empty screenshots.",
    "Failed screenshot loads (e.g. seeded fake paths or wiped uploads) now show a graceful 'Screenshot unavailable' tile via onerror handler.",
    "Click Verify → modal opens with full-size screenshots, hours, subject, notes input, and 4 status buttons.",
])
story.append(Paragraph("Backend", H3))
story.append(Paragraph(
    "POST /api/submission/verify updates the Submission and then idempotently corrects the user's streak / points / counters — "
    "previous status effect is undone before the new one is applied, supporting re-verification without double-counting.",
    BODY))
story.append(PageBreak())


# ─── 13. Deployment ───
story.append(section_box("13. Deployment Architecture"))
story.append(Spacer(1, 8))

story.append(code_block(
    "Browser  →  Netlify (static CDN)  →  fetch()  →  Render.com (Node + Express)  →  MongoDB Atlas\n\n"
    "Frontend host:  darling-bienenstitch-be5932.netlify.app\n"
    "Backend host :  accountastudy.onrender.com/api\n"
    "Database     :  MongoDB Atlas (free M0 cluster)\n"
    "Source       :  github.com/sonusharma2004/AccountaStudy"))

story.append(Paragraph("CI/CD pipeline", H3))
story += bullet_list([
    "<b>Backend:</b> git push origin main → GitHub webhook → Render auto-installs deps and restarts node server.js.",
    "<b>Frontend:</b> netlify deploy --prod --dir=frontend pushes static assets to Netlify's global CDN.",
    "<b>Database:</b> hosted on MongoDB Atlas — connection string set in Render's environment variables (MONGODB_URI).",
])
story.append(Paragraph("Environment variables (backend/.env)", H3))
story.append(code_block(
    "MONGODB_URI=mongodb+srv://<user>:<pass>@cluster0.<id>.mongodb.net/accountastudy\n"
    "JWT_SECRET=<long random string>\n"
    "JWT_EXPIRES_IN=7d\n"
    "PORT=5001\n"
    "NODE_ENV=production\n"
    "MAX_FILE_SIZE=10485760  # 10 MB"))
story.append(PageBreak())


# ─── 14. Local Setup ───
story.append(section_box("14. Quick Local Setup"))
story.append(Spacer(1, 8))
story.append(code_block(
    "# 1. Clone\n"
    "git clone https://github.com/sonusharma2004/AccountaStudy.git\n"
    "cd AccountaStudy\n\n"
    "# 2. Backend\n"
    "cd backend\n"
    "npm install\n"
    "# Create .env with MONGODB_URI, JWT_SECRET, PORT=5001 …\n"
    "npm run seed       # populate demo data\n"
    "npm run dev        # nodemon server.js  →  http://localhost:5001\n\n"
    "# 3. Frontend  (new terminal)\n"
    "cd ../frontend\n"
    "# point API_URL in app.js to http://localhost:5001/api for local dev\n"
    "npx serve . -p 5500    # http://localhost:5500"))
story.append(Paragraph("Demo credentials (from seed.js)", H3))
story.append(kv_table([
    ["student@school.edu / pass123", "Default test student"],
    ["admin@school.edu / admin123", "Admin with verification rights"],
], header=["Email / Password", "Role"]))
story.append(PageBreak())


# ─── 15. Key Snippets ───
story.append(section_box("15. Key Code Snippets to Remember"))
story.append(Spacer(1, 8))

story.append(Paragraph("JWT generation (middleware/auth.js)", H3))
story.append(code_block(
    "const generateToken = (userId) =>\n"
    "  jwt.sign({ id: userId }, process.env.JWT_SECRET,\n"
    "           { expiresIn: process.env.JWT_EXPIRES_IN || '7d' });"))

story.append(Paragraph("Password hash hook (models/User.js)", H3))
story.append(code_block(
    "userSchema.pre('save', async function (next) {\n"
    "  if (!this.isModified('password')) return next();\n"
    "  const salt = await bcrypt.genSalt(12);\n"
    "  this.password = await bcrypt.hash(this.password, salt);\n"
    "  next();\n"
    "});"))

story.append(Paragraph("Unique-per-day submission (models/Submission.js)", H3))
story.append(code_block(
    "submissionSchema.index({ userId: 1, date: 1 }, { unique: true });"))

story.append(Paragraph("Multer storage (config/multer.js)", H3))
story.append(code_block(
    "const storage = multer.diskStorage({\n"
    "  destination: (req, file, cb) => {\n"
    "    if (file.fieldname === 'timerScreenshot') cb(null, './uploads/timer');\n"
    "    else if (file.fieldname === 'questionScreenshot') cb(null, './uploads/questions');\n"
    "    else cb(null, './uploads');\n"
    "  },\n"
    "  filename: (req, file, cb) => {\n"
    "    cb(null, `${req.user.id}_${today}_${Date.now()}${ext}`);\n"
    "  }\n"
    "});"))

story.append(Paragraph("Leaderboard aggregation (controllers/leaderboardController.js)", H3))
story.append(code_block(
    "Submission.aggregate([\n"
    "  { $match: { date: { $gte: start, $lte: end }, status: { $in: ['completed','halfday'] }}},\n"
    "  { $group: { _id: '$userId',\n"
    "              totalHours: { $sum: '$hoursStudied' },\n"
    "              totalPoints: { $sum: '$pointsAwarded' }}},\n"
    "  { $sort:  { totalHours: -1, totalPoints: -1 }}\n"
    "]);"))

story.append(Paragraph("Frontend: protected fetch (frontend/app.js)", H3))
story.append(code_block(
    "function authHeader() {\n"
    "  const token = localStorage.getItem('token');\n"
    "  return token ? { Authorization: `Bearer ${token}` } : {};\n"
    "}\n\n"
    "fetch(`${API_URL}/submission/my`, { headers: { ...authHeader() }});"))
story.append(PageBreak())


# ──────────────────────────────────────────
# VIVA SECTION
# ──────────────────────────────────────────
def _escape_code(text):
    """Escape '<' / '>' for non-allowed HTML tags so ReportLab doesn't mis-parse code samples
    embedded in question/answer text. Allowed tags: b, i, u, br, font, para, sub, sup."""
    import re
    allowed = re.compile(r'^/?(b|i|u|br|font|para|sub|sup)(\s|/?>)', re.IGNORECASE)
    out = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '<':
            end = text.find('>', i)
            if end == -1:
                out.append('&lt;')
                i += 1
                continue
            inner = text[i + 1:end]
            if allowed.match(inner + '>'):
                out.append(text[i:end + 1])
            else:
                out.append('&lt;' + inner.replace('&', '&amp;') + '&gt;')
            i = end + 1
        else:
            out.append(ch)
            i += 1
    return ''.join(out)


def qa(num, q, a):
    story.append(Paragraph(f"Q{num}. {_escape_code(q)}", Q))
    story.append(Paragraph(_escape_code(a), A))


story.append(section_box("16. Viva Questions — BASIC (Q1 – Q15)", color=SUCCESS))
story.append(Spacer(1, 8))

qa(1, "What is the AccountaStudy project about in one sentence?",
   "AccountaStudy is a full-stack web app that enforces daily study consistency by requiring students to submit "
   "timer + question screenshots every day, which an admin verifies to award streaks, points, and a leaderboard rank.")

qa(2, "What is the technology stack used?",
   "<b>Frontend:</b> HTML5, CSS3, Vanilla JavaScript (ES2022), Chart.js. "
   "<b>Backend:</b> Node.js 18 + Express.js 4.19. "
   "<b>Database:</b> MongoDB Atlas with Mongoose ODM 8.4. "
   "<b>Auth:</b> JWT + bcryptjs. <b>Uploads:</b> Multer. "
   "<b>Hosting:</b> Render (backend), Netlify (frontend).")

qa(3, "Why did you choose MongoDB instead of SQL?",
   "Submissions and sessions are document-shaped, the schema evolves over time (we added studentType, leavesRemaining etc. without migrations), and Mongoose lets us "
   "define validation at the application layer. MongoDB Atlas also gives a free managed cloud tier perfect for a college project — no schema-migration overhead, "
   "horizontal scalability, and easy JSON-like queries.")

qa(4, "What is Express.js and why did you use it?",
   "Express.js is a minimalist Node.js web framework that provides routing, middleware support, and request/response abstractions. "
   "I used it because it has very little boilerplate, a huge ecosystem (cors, multer, morgan), and is the industry standard for Node back-ends.")

qa(5, "What does Mongoose do that the native MongoDB driver doesn't?",
   "Mongoose is an Object Data Modelling (ODM) library. It adds: schemas with type enforcement, validators (required, min, max, enum, regex), "
   "middleware (pre-save hooks), virtuals, populate() for joins, and clean async methods. The native driver just gives raw CRUD calls.")

qa(6, "What is JWT and how does it work in your project?",
   "JWT (JSON Web Token) is a compact, URL-safe token format with three Base64-encoded parts — header, payload, signature — separated by dots. "
   "On login the server signs a token containing the user's id with JWT_SECRET (HS256). The frontend stores it in localStorage and sends it in the "
   "Authorization: Bearer header on every protected request. Server verifies the signature on each request — no session store needed, so it scales horizontally.")

qa(7, "Why bcrypt for passwords? Why not SHA-256?",
   "SHA-256 is a fast general-purpose hash — perfect for file integrity but bad for passwords because GPUs can compute billions per second. "
   "bcrypt is intentionally slow (cost factor 12 ≈ 250 ms per hash) and applies an automatic random salt, so identical passwords produce different hashes "
   "and brute-force attacks become impractical.")

qa(8, "How are screenshots uploaded and stored?",
   "The frontend builds a multipart/form-data request with two file fields (timerScreenshot, questionScreenshot). Multer parses it on the backend. "
   "Files are saved to disk under <i>uploads/timer/</i> and <i>uploads/questions/</i> using the pattern <i>userId_date_timestamp.ext</i>. "
   "Only the relative path is stored in the Submission document, and Express serves the uploads folder statically.")

qa(9, "What is CORS and why did you need it?",
   "CORS (Cross-Origin Resource Sharing) is a browser security feature that blocks JavaScript from one origin (e.g. Netlify) from calling APIs on a different origin (Render) "
   "unless the server explicitly allows it. I configured the cors package with a whitelist containing my Netlify domain and any .onrender.com subdomain.")

qa(10, "What does the pre-save hook in the User model do?",
   "It runs automatically before any save() on a User document. It checks if the password field was modified; if yes, it generates a 12-round salt and "
   "replaces the plaintext password with its bcrypt hash. This means controllers never have to remember to hash — it's enforced at the model layer.")

qa(11, "How do you ensure one submission per user per day?",
   "The Submission schema has a compound unique index: <i>{ userId: 1, date: 1 }</i>. MongoDB rejects any insert that violates it with error code 11000, "
   "which my errorHandler middleware converts into a friendly HTTP 409 response saying 'You have already submitted proof for today'.")

qa(12, "What's the difference between authentication and authorization here?",
   "<b>Authentication</b> = 'Who are you?' — verifying the JWT in the <i>protect</i> middleware. "
   "<b>Authorization</b> = 'Are you allowed?' — the <i>adminOnly</i> middleware that runs after protect and rejects any request whose req.user.role isn't 'admin'.")

qa(13, "Why is the password field marked select:false?",
   "So that User.find() and friends never accidentally include the password hash in API responses. "
   "When I do need it (e.g. during login to compare), I explicitly opt in with .select('+password').")

qa(14, "What is Multer's fileFilter doing?",
   "It inspects each incoming file's extension and MIME type. Only jpeg/jpg/png/gif/webp pass; everything else is rejected with an error which Express's errorHandler "
   "converts to a clean HTTP 400 response. This stops users from uploading executables, PDFs, etc.")

qa(15, "What happens when a user clicks 'Start' on the timer?",
   "Frontend POSTs /api/session/start with the chosen subject. The backend silently closes any orphaned isActive session for that user, "
   "creates a new Session document with isActive:true and startTime=now, returns the new id. The frontend stores the id, starts a setInterval to display elapsed seconds, "
   "and applies the focus-mode class to <body> so the UI dims.")

story.append(PageBreak())


# ─── Intermediate ───
story.append(section_box("17. Viva Questions — INTERMEDIATE (Q16 – Q35)", color=ACCENT))
story.append(Spacer(1, 8))

qa(16, "How does the streak system work?",
   "When the admin marks a submission as 'completed' or 'halfday', the controller does <i>student.streak += 1</i>. If status is 'fine', "
   "<i>student.streak = 0</i>. 'leave' doesn't change the streak. The longestStreak field is updated whenever the current streak exceeds it.")

qa(17, "Explain the points system in detail.",
   "Each submission has pointsAwarded based on a status → points map: completed=+100, halfday=+40, leave=0, fine=-20. "
   "The Submission pre-save hook sets pointsAwarded automatically. The user's running 'points' counter is incremented by the verify controller. "
   "If re-verifying, the previous status's effect is undone first so totals never double-count.")

qa(18, "How does the leaderboard differ between modes?",
   "<b>Daily/Weekly:</b> uses a MongoDB aggregation pipeline that $match-es submissions in the date range with status ∈ {completed, halfday}, "
   "$group-s by userId summing hoursStudied + pointsAwarded, then $sort-s desc. "
   "<b>Overall:</b> a simple User.find({role:'student', isActive:true}).sort({totalStudyHours:-1, points:-1}). "
   "Both return an array with rank, name, avatar, totalHours, points.")

qa(19, "What is a MongoDB aggregation pipeline?",
   "It's a sequence of stages that transform documents: $match filters, $group reduces by key, $sort orders, $project shapes the output. "
   "I use it for the leaderboard to compute per-user totals in a single round-trip, which is way faster than fetching all submissions to JS and looping.")

qa(20, "Walk me through the submit-daily-proof flow end-to-end.",
   "1) Student clicks a card (Full/Half/Leave). 2) Frontend builds FormData and POSTs /api/submission/upload with Bearer token. "
   "3) Multer parses files into req.files. 4) Controller validates allowance, screenshots, subject, hours. "
   "5) Creates or updates a Submission with status='pending'. 6) Decrements leavesRemaining or halfDaysRemaining if applicable. "
   "7) Updates user's totalStudyHours. 8) Returns the saved submission with full /uploads URLs so the UI shows it immediately. "
   "9) Admin later verifies → status flips → streak/points update.")

qa(21, "Why is the date field stored as a string 'YYYY-MM-DD' instead of a Date?",
   "Because the business logic needs day-level granularity (one submission per day), not timestamps. "
   "Storing it as a fixed-format string makes equality checks trivial, indexes cheap, and avoids timezone bugs that would happen with Date.")

qa(22, "Tell me about the middleware chain in Express.",
   "Express processes a request through an ordered list of middleware. In my app: 1) CORS, 2) JSON parser, 3) URL-encoded parser, "
   "4) morgan logger (dev only), 5) static /uploads, 6) routers (auth, submission, session, etc.), 7) 404 handler, "
   "8) global errorHandler. Each calls next() to continue, or sends a response to short-circuit.")

qa(23, "What happens if JWT_SECRET is leaked?",
   "Anyone could forge tokens for any user id. I'd need to rotate JWT_SECRET in Render's env vars; all existing tokens would instantly become invalid because "
   "jwt.verify would fail signature check, forcing every user to log in again. That's actually one strength of JWT — secret rotation = global logout.")

qa(24, "How does the focus-mode (Library Mode) UI work?",
   "When the timer starts, the frontend adds a <i>focus-mode</i> class to <body>. CSS rules under <i>body.focus-mode</i> override background to a warm "
   "dimmed gradient, collapse the sidebar, and hide non-essential cards. When the user stops the timer or navigates away, the class is removed and the normal theme returns.")

qa(25, "How do you prevent a deactivated user from continuing to use the app?",
   "The protect middleware loads the user from DB on every request and checks isActive. If false, it returns 403 immediately, so even with a valid token "
   "they can't access protected routes. Admin can toggle isActive via PUT /api/admin/user/:id/toggle.")

qa(26, "Explain how the dashboard rank is computed on the frontend.",
   "On login, the app fetches the overall leaderboard. The dashboard sorts it by totalHours desc, then findIndex matching the current user's id + 1 = rank. "
   "If not found, displays '#—'.")

qa(27, "What is the role of dotenv?",
   "dotenv reads a .env file at startup and merges its key=value pairs into process.env. This keeps secrets (MONGODB_URI, JWT_SECRET) out of source control. "
   "On Render they're set via the dashboard, so the same code works locally and in production.")

qa(28, "How is the upload folder served on the frontend?",
   "The backend has <i>app.use('/uploads', express.static(path.join(__dirname,'uploads')))</i>. Frontend builds absolute URLs via absUploadUrl(path) "
   "= API_ORIGIN + '/' + path, so an <img src='https://accountastudy.onrender.com/uploads/timer/xxx.jpg'> loads directly.")

qa(29, "Why did some seeded screenshots show broken-image icons in the admin view?",
   "Because the seed script inserted relative paths like <i>timer/seed_xxx_2026-05-28.jpg</i> that don't exist on disk. I added an onerror handler to the "
   "<img> tag that swaps the broken image for a clean 'Screenshot unavailable' placeholder, so the admin grid stays presentable.")

qa(30, "How does the system handle a network failure during submission?",
   "Frontend's submitProof() wraps the fetch in try/catch. On failure it shows a toast 'Submission failed'. Multer never starts processing because the request "
   "didn't reach the server, so no half-written documents exist. The student can retry — the unique index prevents duplicates if the first request partially succeeded.")

qa(31, "Tell me about the auto-cleanup of orphaned sessions.",
   "If a student starts a timer, then closes the tab without stopping, the Session stays isActive:true forever. The next start would fail with a 409. "
   "So startSession now finds <i>Session.find({userId, isActive:true})</i> and silently closes each one (sets endTime, computes duration, isActive:false) before "
   "creating the new session. The user sees no error.")

qa(32, "Why is your admin verification idempotent?",
   "Because admins may re-verify a submission (correcting a mistake). The controller compares previousStatus vs new status — if different, it undoes the previous status's "
   "effect on the user (decrements counters, points, streak) before applying the new status. So toggling completed → fine → completed leaves totals consistent.")

qa(33, "How does Mongoose validation help here?",
   "Schemas enforce types, required fields, regex (email, date), enums (status, subject, role, studentType), and min/max ranges (hoursStudied 0.5–24). "
   "If a controller forgets a field, save() throws a ValidationError that errorHandler converts to HTTP 400 with the human-readable message — saves a lot of defensive code.")

qa(34, "Explain how the 6 PM – 7:30 PM submission window banner works.",
   "On the dashboard, updateDeadlineBanner() reads the current local hour and renders a warning if it's within 18:00–19:30 IST. "
   "Today's-proof submitted state replaces the banner with a green confirmation. Currently this is UI-only — the backend doesn't reject out-of-window submissions, "
   "so admins still have the final say.")

qa(35, "How is the project deployed?",
   "Backend is a Node service on Render.com — git push to main triggers an auto-build that runs <i>npm install && node server.js</i>. "
   "Frontend is static HTML/CSS/JS pushed to Netlify via 'netlify deploy --prod --dir=frontend'. Database is MongoDB Atlas — the connection string lives in Render's env vars. "
   "All three are connected via the API_URL constant baked into app.js.")

story.append(PageBreak())


# ─── Advanced & tricky ───
story.append(section_box("18. Viva Questions — ADVANCED & TRICKY (Q36 – Q55)", color=DANGER))
story.append(Spacer(1, 8))

qa(36, "What if two students try to register with the same email simultaneously?",
   "The email field is <i>unique:true</i>, which creates a unique index in MongoDB. The first insert wins; the second hits error code 11000 (duplicate key). "
   "errorHandler converts that to HTTP 409 with 'An account with this email already exists.' Race-condition safe at the DB level.")

qa(37, "Why use JWT instead of session cookies?",
   "Stateless — server doesn't store sessions, so it scales horizontally and works fine on Render's free tier that can spin down. "
   "Tradeoff: you can't easily revoke an individual token (only via secret rotation). For a college project that's acceptable; for a banking app you'd add a token blacklist.")

qa(38, "Render's free tier loses the uploads folder on cold restart. How would you fix this in production?",
   "Move uploads to an object store like AWS S3 / Cloudinary / Backblaze B2. Replace Multer's diskStorage with multer-s3 (or upload-then-stream). "
   "Save only the public URL in the Submission document. The DB stays the same. This also gives CDN-cached images.")

qa(39, "How would you scale this app to 100k students?",
   "1) Replace disk uploads with S3 + CloudFront. 2) Move sessions to Redis if you need rate-limit / blacklist. "
   "3) Add MongoDB indexes (most are already there) and use the M10+ Atlas tier for sharding. 4) Run multiple Node instances behind a load balancer — JWT is stateless so no sticky sessions needed. "
   "5) Cache the leaderboard in Redis with a TTL of, say, 60 seconds — leaderboards rarely need to be perfectly real-time.")

qa(40, "What kind of attacks did you defend against?",
   "<b>Brute force:</b> bcrypt 12 rounds is slow. <b>XSS:</b> use textContent (not innerHTML) for user-supplied text in the UI. "
   "<b>SQL/NoSQL injection:</b> Mongoose with parameterised queries prevents operator injection in basic cases. "
   "<b>File-type attacks:</b> Multer fileFilter + 10MB cap. <b>CSRF:</b> JWTs in localStorage aren't sent automatically by browsers, so CSRF risk is minimal. "
   "<b>Replay:</b> JWT expires in 7 days (could be shortened).")

qa(41, "What is the difference between findOne and findById?",
   "Both return one document. findById is a thin wrapper that converts a string id to ObjectId. findOne accepts any filter object. "
   "Functionally identical for id-based queries; findById is just more semantic.")

qa(42, "Why use Promise.all in fetchAllData?",
   "To run independent network calls in parallel. Sequential awaits would take the sum of latencies; Promise.all takes the max. "
   "For dashboard loading (submissions + sessions + leaderboard) it cuts perceived load time roughly in half.")

qa(43, "Explain the studentType field — why intern vs fulltime?",
   "Some students join as interns (part-time) and have different expectations than full-time aspirants. The field is purely descriptive today (shown in the profile drawer) "
   "but the schema is in place for future logic — e.g. different daily-hour quotas, different allowance counts, role-based analytics.")

qa(44, "How does the half-day / leave allowance auto-deduct?",
   "When uploadSubmission creates a NEW submission with submissionType='leave', userUpdate.$inc.leavesRemaining = -1 is added to findByIdAndUpdate. "
   "Same for halfday. The decrement is skipped on edits (existing pending submission) so editing doesn't double-deduct. The remaining counts are shown on dashboard + submit page; "
   "if 0, the corresponding card is visually disabled.")

qa(45, "What's the difference between PUT, POST, PATCH in your API design?",
   "POST = create a new resource (registration, new session, new submission, verify action). PUT = full update of an existing resource (update-profile, toggle user). "
   "PATCH would be partial update — I chose PUT for clarity even though most updates are partial. DELETE = remove (admin/user/:id).")

qa(46, "What happens internally when bcrypt.hash is called?",
   "1) Generate a random 16-byte salt. 2) Run the Blowfish-based bcrypt KDF (key derivation function) for 2^cost iterations (cost=12 ⇒ 4096 iterations of internal rounds). "
   "3) Produce a 60-char string that encodes algorithm, cost, salt, and hash. So the same password produces a different output every time, and verifying needs the stored salt — which is embedded in the hash itself.")

qa(47, "What edge cases did you handle in the verify controller?",
   "1) Submission not found → 404. 2) Invalid status → 400. 3) Re-verification — undo old status effects to keep totals correct. "
   "4) Streak going negative → Math.max(0, …). 5) Points going negative → Math.max(0, …). 6) longestStreak only updated if current streak exceeds it.")

qa(48, "Could a malicious student craft a JWT for someone else?",
   "Only if they obtain JWT_SECRET. The signature is HMAC-SHA256 over (header.payload, JWT_SECRET). Without the secret, jwt.verify will throw JsonWebTokenError "
   "and the request is rejected. The token's payload (their id) is base64-encoded and visible, but that's expected — security comes from the signature, not secrecy of payload.")

qa(49, "Why didn't you use a frontend framework like React?",
   "1) Project scope is small enough that vanilla JS keeps the bundle ~50KB instead of React's ~150KB. 2) No build pipeline needed — deploys instantly. "
   "3) Demonstrates fundamentals — fetch, DOM, state. 4) Hosts trivially on any CDN. For a larger team or richer UI, React would absolutely be the right call.")

qa(50, "How would you add real-time updates (e.g. live leaderboard)?",
   "Add Socket.IO or native WebSockets to the Express server. On verifySubmission, emit a 'leaderboardChanged' event; clients on the Leaderboard page subscribe and re-fetch. "
   "Alternatively, use Server-Sent Events for a one-way push or just poll every 30 seconds with setInterval.")

qa(51, "How are the analytics charts rendered?",
   "Chart.js is loaded via CDN. On the Analytics page I build datasets from S.submissions and S.sessions (filtered to the last 30 days) and instantiate "
   "new Chart(ctx, { type:'bar'|'doughnut'|'line', data, options }). On nav away, old chart instances are destroyed to prevent memory leaks.")

qa(52, "Tell me one bug you faced and how you fixed it.",
   "Submission validation kept rejecting leaves because I was passing subject='Leave', but the enum only allows Mathematics / Physics / … / Other. "
   "I changed the frontend to send 'Other' for leave submissions and made the leave path skip image validation. That fixed both errors at once.")

qa(53, "What does the errorHandler middleware do specifically?",
   "It's a 4-arg middleware (err, req, res, next) registered last. It maps known error types to friendly responses: CastError → 404, duplicate-key 11000 → 409 with field-specific message, "
   "ValidationError → 400 with joined messages, Multer LIMIT_FILE_SIZE → 400 'File too large', file-type rejection → 400. In dev mode it also includes the stack trace.")

qa(54, "Why store hours both on the Submission and as a totalStudyHours on the User?",
   "Submissions are the source of truth (auditable, per-day records). totalStudyHours on User is a denormalised running total to make profile/dashboard queries O(1) instead of "
   "aggregating across all submissions every page load. The trade-off is the controller must keep it in sync (which I do via $inc on every relevant action).")

qa(55, "If I asked you to add a feature where students can comment on each other's submissions, how would you do it?",
   "1) Add a Comment model: { submissionId, userId, text, createdAt }. 2) Add routes POST /api/submission/:id/comments and GET /api/submission/:id/comments (protected). "
   "3) In the controller, populate userId to return name/avatar. 4) On the frontend, show comment count on each card, and a comments drawer when the card is clicked. "
   "5) Add moderation — only the comment author or admin can delete. Database changes are non-breaking, so deployment is a simple git push.")

story.append(PageBreak())


# ─── Cheat-sheet ───
story.append(section_box("19. Quick Revision Cheat-Sheet"))
story.append(Spacer(1, 8))
story.append(Paragraph("Memorise these numbers and one-liners — common follow-up viva drills.", BODY))

story.append(Paragraph("Tech Stack in 6 words", H3))
story.append(Paragraph(
    "<b>HTML + CSS + JS + Node + Express + MongoDB.</b> Add JWT for auth, Multer for uploads, Chart.js for graphs, Render + Netlify + Atlas for deployment.",
    BODY))

story.append(Paragraph("Points / Status Map", H3))
story.append(kv_table([
    ["completed", "+100"], ["halfday", "+40"],
    ["leave", "0"], ["fine", "-20"],
], header=["Status", "Points"]))

story.append(Paragraph("Counts to Remember", H3))
story.append(kv_table([
    ["Leaves per term", "3"],
    ["Half days per term", "3"],
    ["Subjects enum size", "9"],
    ["JWT default expiry", "7 days"],
    ["bcrypt cost factor", "12"],
    ["Max file size", "10 MB"],
    ["Submission window", "6 PM – 7:30 PM"],
    ["Backend port", "5001 (local) / 10000 (Render-assigned)"],
    ["Allowed image types", "jpeg, jpg, png, gif, webp"],
], header=["Quantity", "Value"]))

story.append(Paragraph("Files You Should Be Able to Find Instantly", H3))
story.append(kv_table([
    ["Entry point", "backend/server.js"],
    ["DB connection", "backend/config/db.js"],
    ["Auth middleware", "backend/middleware/auth.js"],
    ["User schema", "backend/models/User.js"],
    ["Submission schema", "backend/models/Submission.js"],
    ["Submission controller", "backend/controllers/submissionController.js"],
    ["Leaderboard controller", "backend/controllers/leaderboardController.js"],
    ["Frontend logic", "frontend/app.js"],
    ["Frontend markup", "frontend/index.html"],
    ["Seed script", "backend/scripts/seed.js"],
], header=["What", "Path"]))

story.append(Paragraph("Top 5 Talking Points for the Panel", H3))
story += bullet_list([
    "<b>End-to-end ownership</b> — designed schema, built REST API, frontend, deployed to live cloud — all alone.",
    "<b>Real-world problem solving</b> — screenshot-based proof eliminates self-reporting dishonesty.",
    "<b>Security-conscious</b> — bcrypt 12 rounds, JWT, CORS whitelist, file-type filter, validation on every model.",
    "<b>Production-grade UX</b> — focus mode, profile drawer, graceful image-load fallback, leave allowance auto-deduction.",
    "<b>Aggregation pipelines</b> — used MongoDB's $match/$group/$sort to compute leaderboards efficiently in one DB round-trip.",
])

story.append(Spacer(1, 14))
story.append(Paragraph(
    "<b>Final tip:</b> If you don't know an answer, talk through how you'd find it — examiners value reasoning over memorisation.",
    NOTE))

# ───── Build PDF ─────
doc = SimpleDocTemplate(
    OUTPUT, pagesize=A4,
    leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    topMargin=1.6 * cm, bottomMargin=1.5 * cm,
    title="AccountaStudy — Revision & Viva Guide",
    author="Sonu Sharma",
)
doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
print(f"✅ Generated: {OUTPUT}")
