from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for
from app.services.db_service import get_subjects, get_subject_by_code, get_generated_note, save_generated_note
from app.services.llm_service import generate_text_sync
from app.config import Config
from database import get_user_ai_config
from app.services.openrouter_service import get_server_api_key, get_default_model, validate_model

subjects_bp = Blueprint('subjects', __name__)

# Detailed prompt templates for each generation type
PROMPT_TEMPLATES = {
    "overview": """You are an expert MCA professor. Generate a comprehensive overview for the subject "{name}" (Code: {code}, Semester {semester}).

Include the following sections in Markdown:
## Subject Overview
A detailed paragraph explaining what this subject covers and why it matters.

## Learning Outcomes
List 6-8 specific learning outcomes students should achieve.

## Important Topics
List the most important topics for exams.

## Practical Applications
Explain real-world applications of this subject.

## Study Tips
Give 5-6 actionable study tips specific to this subject.

## Recommended Books
List 3-4 standard textbooks with author names.

## Recommended YouTube Channels
List 3-4 helpful YouTube channels or playlists for this subject.

Be detailed, accurate, and helpful for MCA students.""",

    "summary": """You are an expert MCA professor. Generate comprehensive module-wise study notes for the subject "{name}" (Code: {code}, Semester {semester}).

Structure the notes as follows in Markdown:

## Module-wise Notes
Create detailed notes for each module/unit covering key concepts, definitions, formulas, and examples.

## Summary of Key Points
A bulleted list of the most critical points to remember.

## Frequently Asked Questions
List 10 commonly asked questions with brief answers.

## Exam Preparation Tips
Specific tips for preparing for the exam of this subject.

## Important Formulas / Definitions
List all critical formulas and definitions.

Make it thorough, well-organized, and exam-focused for MCA students.""",

    "paper_5m": """You are an expert MCA professor. Generate a set of 5-marks exam questions for the subject "{name}" (Code: {code}, Semester {semester}).

Generate exactly 15 questions worth 5 marks each in Markdown format.

For each question:
- Write the question clearly
- Provide a model answer that would score full marks (approximately 200 words per answer)
- Include diagrams described in text where appropriate

Cover all modules/units of the syllabus evenly. Include a mix of:
- Explain/Describe type questions
- Compare and contrast questions
- Short numerical/code problems
- Definition-based questions

Format each as:
### Q1. [Question text] (5 Marks)
**Answer:** [Detailed model answer]

Make it realistic and exam-focused for MCA students.""",

    "paper_10m": """You are an expert MCA professor. Generate a set of 10-marks exam questions for the subject "{name}" (Code: {code}, Semester {semester}).

Generate exactly 10 questions worth 10 marks each in Markdown format.

For each question:
- Write the question clearly (may have sub-parts a, b)
- Provide a comprehensive model answer (approximately 400-500 words per answer)
- Include algorithms, code examples, diagrams described in text where appropriate

Cover all modules/units of the syllabus evenly. Include a mix of:
- Long answer theory questions
- Algorithm/code writing questions
- Case study or scenario-based questions
- Proof/derivation questions (if applicable)

Format each as:
### Q1. [Question text] (10 Marks)
**Answer:** [Detailed model answer]

Make it realistic and exam-focused for MCA students.""",

    "viva": """You are an expert MCA professor. Generate a comprehensive set of viva voce questions for the subject "{name}" (Code: {code}, Semester {semester}).

Generate 25 viva questions organized by difficulty in Markdown format.

## Basic Level Questions (10 questions)
Simple definition and concept questions with one-line answers.

## Intermediate Level Questions (10 questions)  
Questions requiring explanation and understanding with 2-3 line answers.

## Advanced Level Questions (5 questions)
Deep conceptual questions that test thorough understanding with detailed answers.

For each question provide:
### Q: [Question]
**A:** [Clear, concise answer]

Also include:
## Tips for Viva Preparation
5 practical tips for performing well in the viva.

Make it realistic and helpful for MCA students preparing for lab viva or external exams."""
}

@subjects_bp.route('/api/subjects', methods=['GET'])
def get_subjects_api():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    subjects = get_subjects()
    return jsonify({"subjects": subjects})

@subjects_bp.route('/subject/<string:code>', methods=['GET'])
def subject_page(code):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    subject = get_subject_by_code(code)
    if not subject:
        return "Subject not found", 404
        
    return render_template('subject.html', subject=subject)

@subjects_bp.route('/api/generate_notes', methods=['POST'])
def generate_notes():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    subject_code = data.get("subject_code")
    note_type = data.get("note_type")
    
    if not subject_code or not note_type:
        return jsonify({"error": "Missing subject_code or note_type"}), 400
    
    subject = get_subject_by_code(subject_code)
    if not subject:
        return jsonify({"error": "Subject not found"}), 404
        
    # Check cache first
    cached_note = get_generated_note(subject_code, note_type)
    if cached_note:
        return jsonify({"content": cached_note})
        
    # Resolve the authenticated user's personal key first, then the
    # server default key. Neither key is exposed to the browser.
    try:
        api_config = get_user_ai_config(session['user_id'])
    except RuntimeError:
        return jsonify({"error": "Stored personal API key could not be loaded. Please remove it and add it again."}), 500

    api_key = api_config.get("api_key") or get_server_api_key()
    model = api_config.get("model") or get_default_model()

    if not api_key:
        return jsonify({"error": "AI service is not configured on the server."}), 503

    if not validate_model(model, api_key):
        return jsonify({"error": "This model is currently unavailable. Please select another model in Settings."}), 400

    # Build rich prompt from template
    prompt_template = PROMPT_TEMPLATES.get(note_type)
    if not prompt_template:
        return jsonify({"error": f"Unknown note type: {note_type}"}), 400
        
    prompt = prompt_template.format(
        name=subject['name'],
        code=subject['code'],
        semester=subject['semester']
    )
    
    content, err_msg = generate_text_sync(prompt, model, api_key)
    if err_msg or not content:
        return jsonify({"error": err_msg or "Failed to generate content. Please check your API key and model in Settings."}), 500
        
    # Cache the result for future use
    save_generated_note(subject_code, note_type, content)
    return jsonify({"content": content})
