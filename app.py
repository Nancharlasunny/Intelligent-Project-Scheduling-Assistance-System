from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import secrets
from bson import ObjectId

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

client = MongoClient('mongodb://localhost:27017/')
db = client['project_scheduling_db']

users_collection = db['users']
sessions_collection = db['sessions']
skill_requirements_collection = db['skill_requirements']
project_types_collection = db['project_types']
student_skills_collection = db['student_skills']
skill_assessments_collection = db['skill_assessments']
skill_gaps_collection = db['skill_gaps']
comparison_reports_collection = db['comparison_reports']
generated_reports_collection = db['generated_reports']
project_schedules_collection = db['project_schedules']
milestones_collection = db['milestones']
historical_patterns_collection = db['historical_patterns']
recommendations_collection = db['recommendations']
learning_resources_collection = db['learning_resources']
progress_logs_collection = db['progress_logs']
milestone_status_collection = db['milestone_status']
alerts_collection = db['alerts']
career_paths_collection = db['career_paths']
industry_requirements_collection = db['industry_requirements']
faculty_feedback_collection = db['faculty_feedback']
mentoring_sessions_collection = db['mentoring_sessions']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'faculty':
            flash('Faculty access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            flash('Student access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def analyze_skill_gaps(required_skills, current_skills):
    gap_list = []
    
    for skill in required_skills:
        required_level = skill['proficiency_level']
        skill_name = skill['name']
        importance = skill.get('importance', 3)
        category = skill.get('category', 'technical')
        
        current_level = 0
        for curr_skill in current_skills:
            if curr_skill['name'] == skill_name:
                current_level = curr_skill['level']
                break
        
        gap_value = required_level - current_level
        
        if gap_value > 0:
            priority = calculate_priority(gap_value, importance)
            gap_record = {
                'skill_name': skill_name,
                'required': required_level,
                'current': current_level,
                'gap': gap_value,
                'priority': priority,
                'category': category
            }
            gap_list.append(gap_record)
    
    gap_list.sort(key=lambda x: x['priority'], reverse=True)
    return gap_list

def calculate_priority(gap_value, importance_weight):
    priority_score = gap_value * importance_weight
    
    if gap_value >= 3:
        priority_score *= 1.5
    elif gap_value >= 2:
        priority_score *= 1.2
    
    return priority_score

def generate_recommendations(skill_gaps, learning_resources, student_profile):
    recommendations = []
    
    for gap in skill_gaps:
        matching_resources = []
        
        for resource in learning_resources:
            score = 0
            
            if resource['skill'] == gap['skill_name']:
                score += 40
            
            if resource['difficulty_level'] == gap['current'] + 1:
                score += 30
            elif resource['difficulty_level'] == gap['current'] + 2:
                score += 15
            
            if resource['duration'] <= student_profile.get('available_hours', 10):
                score += 20
            else:
                score += 5
            
            if resource['format'] in student_profile.get('preferred_formats', ['video', 'article']):
                score += 10
            
            if score >= 40:
                matching_resources.append({
                    'resource': resource,
                    'score': score,
                    'relevance': score / 100
                })
        
        matching_resources.sort(key=lambda x: x['score'], reverse=True)
        recommendations.extend(matching_resources[:3])
    
    return recommendations

def calculate_avg_proficiency(required_skills, student_skills_dict):
    total = 0
    count = len(required_skills)
    
    if count == 0:
        return 0
    
    for skill in required_skills:
        skill_name = skill['name']
        if skill_name in student_skills_dict:
            total += student_skills_dict[skill_name]
        else:
            total += 0
    
    return total / count

def create_intelligent_schedule(project_tasks, student_skills_dict, skill_gaps, project_start_date):
    schedule = []
    task_end_dates = {}
    
    for task in project_tasks:
        base_duration = task['estimated_hours']
        required_skills = task.get('required_skills', [])
        
        avg_proficiency = calculate_avg_proficiency(required_skills, student_skills_dict)
        
        if avg_proficiency < 2:
            duration_multiplier = 2.0
        elif avg_proficiency < 3:
            duration_multiplier = 1.5
        elif avg_proficiency < 4:
            duration_multiplier = 1.2
        else:
            duration_multiplier = 1.0
        
        adjusted_duration = base_duration * duration_multiplier
        
        gap_buffer = 0
        for skill in required_skills:
            for gap in skill_gaps:
                if gap['skill_name'] == skill['name']:
                    gap_buffer += (gap['gap'] * 2)
        
        total_duration = adjusted_duration + gap_buffer
        
        dependencies = task.get('dependencies', [])
        if not dependencies:
            start_date = project_start_date
        else:
            max_end_date = project_start_date
            for dep_id in dependencies:
                if dep_id in task_end_dates:
                    dep_end = task_end_dates[dep_id]
                    if dep_end > max_end_date:
                        max_end_date = dep_end
            start_date = max_end_date
        
        end_date = start_date + timedelta(days=total_duration / 8)
        
        task_end_dates[task['id']] = end_date
        
        milestone = {
            'task_id': task['id'],
            'task_name': task['name'],
            'start_date': start_date,
            'end_date': end_date,
            'duration': total_duration,
            'buffer': gap_buffer,
            'dependencies': dependencies,
            'critical': task.get('critical', False)
        }
        schedule.append(milestone)
    
    return schedule

def detect_delays(milestone_schedule, progress_logs_list, current_date):
    alerts = []
    
    for milestone in milestone_schedule:
        progress_percentage = 0
        for log in progress_logs_list:
            if log['task_id'] == milestone['task_id']:
                progress_percentage = log['completion']
        
        expected_progress = calculate_expected_progress(milestone, current_date)
        deviation = expected_progress - progress_percentage
        
        if current_date > milestone['end_date'] and progress_percentage < 100:
            days_overdue = (current_date - milestone['end_date']).days
            alert = {
                'type': 'OVERDUE',
                'severity': 'HIGH',
                'milestone': milestone['task_name'],
                'message': f"Milestone overdue by {days_overdue} days",
                'created_at': datetime.now()
            }
            alerts.append(alert)
        elif deviation >= 20:
            days_behind = int((deviation / 100) * ((milestone['end_date'] - milestone['start_date']).days))
            alert = {
                'type': 'AT_RISK',
                'severity': 'MEDIUM',
                'milestone': milestone['task_name'],
                'message': f"Milestone at risk. {days_behind} days behind schedule",
                'created_at': datetime.now()
            }
            alerts.append(alert)
        elif deviation >= 10:
            alert = {
                'type': 'WARNING',
                'severity': 'LOW',
                'milestone': milestone['task_name'],
                'message': "Minor delay detected. Monitor progress closely",
                'created_at': datetime.now()
            }
            alerts.append(alert)
    
    return alerts

def calculate_expected_progress(milestone, current_date):
    if current_date < milestone['start_date']:
        return 0
    elif current_date > milestone['end_date']:
        return 100
    else:
        elapsed = (current_date - milestone['start_date']).total_seconds()
        total_duration = (milestone['end_date'] - milestone['start_date']).total_seconds()
        return (elapsed / total_duration) * 100

def prioritize_learning_path(skill_gaps, project_timeline_days, career_goals):
    learning_items = []
    
    for gap in skill_gaps:
        urgency_score = (gap['gap'] / 5) * 5
        
        career_relevance = 3
        for goal in career_goals:
            if gap['skill_name'] in goal.get('required_skills', []):
                career_relevance = 5
                break
        
        difficulty_score = gap['gap']
        importance = gap['priority'] / 10
        
        priority_score = (
            urgency_score * 0.4 +
            career_relevance * 0.3 +
            (5 - difficulty_score) * 0.2 +
            importance * 0.1
        )
        
        learning_item = {
            'skill': gap['skill_name'],
            'priority_score': priority_score,
            'urgency': urgency_score,
            'career_value': career_relevance,
            'estimated_time': gap['gap'] * 10,
            'gap_value': gap['gap']
        }
        learning_items.append(learning_item)
    
    learning_items.sort(key=lambda x: x['priority_score'], reverse=True)
    
    learning_path = []
    cumulative_time = 0
    
    for item in learning_items:
        if cumulative_time + item['estimated_time'] <= project_timeline_days * 24:
            learning_path.append({
                'sequence': len(learning_path) + 1,
                'skill': item['skill'],
                'start_week': cumulative_time / (7 * 24),
                'duration_weeks': item['estimated_time'] / (7 * 24),
                'priority_score': item['priority_score']
            })
            cumulative_time += item['estimated_time']
    
    return learning_path

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
        elif session.get('role') == 'faculty':
            return redirect(url_for('faculty_dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        full_name = request.form.get('full_name')
        
        if users_collection.find_one({'email': email}):
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        
        user = {
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': role,
            'full_name': full_name,
            'created_at': datetime.now(),
            'profile': {
                'available_hours': 10,
                'preferred_formats': ['video', 'article', 'practice']
            }
        }
        
        result = users_collection.insert_one(user)
        
        if role == 'student':
            student_skills_collection.insert_one({
                'user_id': str(result.inserted_id),
                'skills': []
            })
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = users_collection.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            session.permanent = True
            
            session_record = {
                'user_id': str(user['_id']),
                'login_time': datetime.now(),
                'ip_address': request.remote_addr
            }
            sessions_collection.insert_one(session_record)
            
            flash(f'Welcome {user["full_name"]}!', 'success')
            
            if user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
            else:
                return redirect(url_for('faculty_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/student/dashboard')
@login_required
@student_required
def student_dashboard():
    user_id = session['user_id']
    
    student_skills = student_skills_collection.find_one({'user_id': user_id})
    skill_count = len(student_skills['skills']) if student_skills else 0
    
    gaps = list(skill_gaps_collection.find({'user_id': user_id}).sort('created_at', -1).limit(1))
    gap_count = len(gaps[0]['gaps']) if gaps else 0
    
    projects = list(project_schedules_collection.find({'user_id': user_id}))
    project_count = len(projects)
    
    recent_alerts = list(alerts_collection.find({'user_id': user_id}).sort('created_at', -1).limit(5))
    
    return render_template('student_dashboard.html', 
                         skill_count=skill_count,
                         gap_count=gap_count,
                         project_count=project_count,
                         recent_alerts=recent_alerts)

@app.route('/faculty/dashboard')
@login_required
@faculty_required
def faculty_dashboard():
    students = list(users_collection.find({'role': 'student'}))
    student_count = len(students)
    
    all_projects = list(project_schedules_collection.find())
    project_count = len(all_projects)
    
    all_skill_reqs = list(skill_requirements_collection.find({'created_by': session['user_id']}))
    skill_req_count = len(all_skill_reqs)
    
    pending_sessions = list(mentoring_sessions_collection.find({
        'faculty_id': session['user_id'],
        'status': 'pending'
    }))
    
    return render_template('faculty_dashboard.html',
                         student_count=student_count,
                         project_count=project_count,
                         skill_req_count=skill_req_count,
                         pending_sessions=pending_sessions)

@app.route('/skill-assessment', methods=['GET', 'POST'])
@login_required
@student_required
def skill_assessment():
    if request.method == 'POST':
        skills_data = []
        skill_names = request.form.getlist('skill_name[]')
        skill_levels = request.form.getlist('skill_level[]')
        skill_categories = request.form.getlist('skill_category[]')
        
        for i in range(len(skill_names)):
            if skill_names[i]:
                skills_data.append({
                    'name': skill_names[i],
                    'level': int(skill_levels[i]),
                    'category': skill_categories[i],
                    'assessed_at': datetime.now()
                })
        
        student_skills_collection.update_one(
            {'user_id': session['user_id']},
            {'$set': {'skills': skills_data, 'updated_at': datetime.now()}},
            upsert=True
        )
        
        assessment_record = {
            'user_id': session['user_id'],
            'skills': skills_data,
            'assessment_date': datetime.now(),
            'assessment_type': 'self'
        }
        skill_assessments_collection.insert_one(assessment_record)
        
        flash('Skills assessed successfully!', 'success')
        return redirect(url_for('student_dashboard'))
    
    current_skills = student_skills_collection.find_one({'user_id': session['user_id']})
    return render_template('skill_assessment.html', current_skills=current_skills)

@app.route('/skill-requirements', methods=['GET', 'POST'])
@login_required
@faculty_required
def skill_requirements():
    if request.method == 'POST':
        project_type = request.form.get('project_type')
        description = request.form.get('description')
        
        skills_data = []
        skill_names = request.form.getlist('skill_name[]')
        proficiency_levels = request.form.getlist('proficiency_level[]')
        importance_weights = request.form.getlist('importance[]')
        skill_categories = request.form.getlist('category[]')
        
        for i in range(len(skill_names)):
            if skill_names[i]:
                skills_data.append({
                    'name': skill_names[i],
                    'proficiency_level': int(proficiency_levels[i]),
                    'importance': int(importance_weights[i]),
                    'category': skill_categories[i]
                })
        
        requirement = {
            'project_type': project_type,
            'description': description,
            'skills': skills_data,
            'created_by': session['user_id'],
            'created_at': datetime.now()
        }
        
        skill_requirements_collection.insert_one(requirement)
        
        project_types_collection.update_one(
            {'name': project_type},
            {'$set': {'name': project_type, 'description': description, 'updated_at': datetime.now()}},
            upsert=True
        )
        
        flash('Skill requirements created successfully!', 'success')
        return redirect(url_for('faculty_dashboard'))
    
    requirements = list(skill_requirements_collection.find({'created_by': session['user_id']}))
    return render_template('skill_requirements.html', requirements=requirements)

@app.route('/gap-analysis', methods=['GET', 'POST'])
@login_required
@student_required
def gap_analysis():
    if request.method == 'POST':
        project_type = request.form.get('project_type')
        
        requirement = skill_requirements_collection.find_one({'project_type': project_type})
        
        if not requirement:
            flash('No skill requirements found for this project type', 'warning')
            return redirect(url_for('gap_analysis'))
        
        student_skills = student_skills_collection.find_one({'user_id': session['user_id']})
        current_skills = student_skills['skills'] if student_skills else []
        
        gaps = analyze_skill_gaps(requirement['skills'], current_skills)
        
        gap_record = {
            'user_id': session['user_id'],
            'project_type': project_type,
            'gaps': gaps,
            'created_at': datetime.now()
        }
        skill_gaps_collection.insert_one(gap_record)
        
        comparison_report = {
            'user_id': session['user_id'],
            'project_type': project_type,
            'required_skills': requirement['skills'],
            'current_skills': current_skills,
            'gaps': gaps,
            'generated_at': datetime.now()
        }
        comparison_reports_collection.insert_one(comparison_report)
        
        flash('Gap analysis completed successfully!', 'success')
        return redirect(url_for('view_gap_analysis'))
    
    project_types = list(project_types_collection.find())
    return render_template('gap_analysis.html', project_types=project_types)

@app.route('/view-gap-analysis')
@login_required
@student_required
def view_gap_analysis():
    latest_report = comparison_reports_collection.find_one(
        {'user_id': session['user_id']},
        sort=[('generated_at', -1)]
    )
    
    return render_template('gap_analysis.html', 
                         report=latest_report,
                         view_mode=True)

@app.route('/project-schedule', methods=['GET', 'POST'])
@login_required
@student_required
def project_schedule():
    if request.method == 'POST':
        project_name = request.form.get('project_name')
        project_type = request.form.get('project_type')
        start_date_str = request.form.get('start_date')
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        task_names = request.form.getlist('task_name[]')
        task_hours = request.form.getlist('task_hours[]')
        task_dependencies = request.form.getlist('task_dependencies[]')
        
        tasks = []
        for i in range(len(task_names)):
            if task_names[i]:
                deps = [int(d) for d in task_dependencies[i].split(',') if d.strip().isdigit()]
                tasks.append({
                    'id': i + 1,
                    'name': task_names[i],
                    'estimated_hours': float(task_hours[i]),
                    'dependencies': deps,
                    'required_skills': [],
                    'critical': False
                })
        
        student_skills = student_skills_collection.find_one({'user_id': session['user_id']})
        student_skills_dict = {}
        if student_skills:
            for skill in student_skills['skills']:
                student_skills_dict[skill['name']] = skill['level']
        
        latest_gaps = skill_gaps_collection.find_one(
            {'user_id': session['user_id']},
            sort=[('created_at', -1)]
        )
        gaps = latest_gaps['gaps'] if latest_gaps else []
        
        schedule = create_intelligent_schedule(tasks, student_skills_dict, gaps, start_date)
        
        project_record = {
            'user_id': session['user_id'],
            'project_name': project_name,
            'project_type': project_type,
            'start_date': start_date,
            'tasks': tasks,
            'schedule': schedule,
            'created_at': datetime.now()
        }
        project_schedules_collection.insert_one(project_record)
        
        for milestone in schedule:
            milestones_collection.insert_one({
                'project_id': str(project_record['_id']) if '_id' in project_record else None,
                'user_id': session['user_id'],
                'task_id': milestone['task_id'],
                'task_name': milestone['task_name'],
                'start_date': milestone['start_date'],
                'end_date': milestone['end_date'],
                'duration': milestone['duration'],
                'status': 'pending'
            })
        
        flash('Project schedule created successfully!', 'success')
        return redirect(url_for('view_project_schedule'))
    
    project_types = list(project_types_collection.find())
    return render_template('project_schedule.html', project_types=project_types)

@app.route('/view-project-schedule')
@login_required
@student_required
def view_project_schedule():
    latest_project = project_schedules_collection.find_one(
        {'user_id': session['user_id']},
        sort=[('created_at', -1)]
    )
    
    return render_template('project_schedule.html',
                         project=latest_project,
                         view_mode=True)

@app.route('/recommendations')
@login_required
@student_required
def recommendations():
    latest_gaps = skill_gaps_collection.find_one(
        {'user_id': session['user_id']},
        sort=[('created_at', -1)]
    )
    
    if not latest_gaps:
        flash('Please complete gap analysis first', 'warning')
        return redirect(url_for('gap_analysis'))
    
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    student_profile = user.get('profile', {})
    
    all_resources = list(learning_resources_collection.find())
    
    if not all_resources:
        default_resources = []
        for gap in latest_gaps['gaps']:
            for level in range(1, 6):
                default_resources.append({
                    'skill': gap['skill_name'],
                    'title': f"{gap['skill_name']} - Level {level}",
                    'difficulty_level': level,
                    'duration': 5 + level * 2,
                    'format': 'video' if level <= 3 else 'practice',
                    'url': f"https://example.com/learn/{gap['skill_name'].replace(' ', '-').lower()}"
                })
        
        if default_resources:
            learning_resources_collection.insert_many(default_resources)
            all_resources = default_resources
    
    recommended = generate_recommendations(latest_gaps['gaps'], all_resources, student_profile)
    
    recommendations_collection.update_one(
        {'user_id': session['user_id']},
        {'$set': {
            'recommendations': recommended,
            'generated_at': datetime.now()
        }},
        upsert=True
    )
    
    return render_template('recommendations.html', recommendations=recommended, gaps=latest_gaps['gaps'])

@app.route('/progress-tracking', methods=['GET', 'POST'])
@login_required
@student_required
def progress_tracking():
    if request.method == 'POST':
        task_id = int(request.form.get('task_id'))
        completion = float(request.form.get('completion'))
        notes = request.form.get('notes', '')
        
        progress_entry = {
            'user_id': session['user_id'],
            'task_id': task_id,
            'completion': completion,
            'notes': notes,
            'timestamp': datetime.now()
        }
        progress_logs_collection.insert_one(progress_entry)
        
        milestone_status_collection.update_one(
            {'user_id': session['user_id'], 'task_id': task_id},
            {'$set': {'completion': completion, 'updated_at': datetime.now()}},
            upsert=True
        )
        
        latest_project = project_schedules_collection.find_one(
            {'user_id': session['user_id']},
            sort=[('created_at', -1)]
        )
        
        if latest_project:
            schedule = latest_project['schedule']
            progress_logs = list(progress_logs_collection.find({'user_id': session['user_id']}))
            alerts = detect_delays(schedule, progress_logs, datetime.now())
            
            for alert in alerts:
                alert['user_id'] = session['user_id']
                alerts_collection.insert_one(alert)
        
        flash('Progress updated successfully!', 'success')
        return redirect(url_for('progress_tracking'))
    
    latest_project = project_schedules_collection.find_one(
        {'user_id': session['user_id']},
        sort=[('created_at', -1)]
    )
    
    progress_logs = []
    if latest_project:
        progress_logs = list(progress_logs_collection.find({'user_id': session['user_id']}).sort('timestamp', -1))
    
    recent_alerts = list(alerts_collection.find({'user_id': session['user_id']}).sort('created_at', -1).limit(10))
    
    return render_template('progress_tracking.html',
                         project=latest_project,
                         progress_logs=progress_logs,
                         alerts=recent_alerts)

@app.route('/career-planning', methods=['GET', 'POST'])
@login_required
@student_required
def career_planning():
    if request.method == 'POST':
        career_goal = request.form.get('career_goal')
        target_industry = request.form.get('target_industry')
        timeline_months = int(request.form.get('timeline_months', 12))
        
        industry_req = industry_requirements_collection.find_one({'industry': target_industry})
        
        if not industry_req:
            industry_req = {
                'industry': target_industry,
                'required_skills': ['Python', 'Data Analysis', 'Machine Learning', 'Communication'],
                'created_at': datetime.now()
            }
            industry_requirements_collection.insert_one(industry_req)
        
        career_path = {
            'user_id': session['user_id'],
            'career_goal': career_goal,
            'target_industry': target_industry,
            'timeline_months': timeline_months,
            'required_skills': industry_req['required_skills'],
            'created_at': datetime.now()
        }
        career_paths_collection.insert_one(career_path)
        
        latest_gaps = skill_gaps_collection.find_one(
            {'user_id': session['user_id']},
            sort=[('created_at', -1)]
        )
        
        if latest_gaps:
            career_goals = [{'required_skills': industry_req['required_skills']}]
            learning_path = prioritize_learning_path(
                latest_gaps['gaps'],
                timeline_months * 30,
                career_goals
            )
            
            career_paths_collection.update_one(
                {'_id': career_path['_id']},
                {'$set': {'learning_path': learning_path}}
            )
        
        flash('Career plan created successfully!', 'success')
        return redirect(url_for('career_planning'))
    
    user_career_path = career_paths_collection.find_one(
        {'user_id': session['user_id']},
        sort=[('created_at', -1)]
    )
    
    industries = list(industry_requirements_collection.find())
    
    return render_template('career_planning.html',
                         career_path=user_career_path,
                         industries=industries)

@app.route('/mentoring', methods=['GET', 'POST'])
@login_required
def mentoring():
    if session.get('role') == 'faculty':
        students = list(users_collection.find({'role': 'student'}))
        
        student_progress = []
        for student in students:
            student_id = str(student['_id'])
            
            latest_project = project_schedules_collection.find_one(
                {'user_id': student_id},
                sort=[('created_at', -1)]
            )
            
            progress_logs = list(progress_logs_collection.find({'user_id': student_id}))
            
            overall_progress = 0
            if latest_project and progress_logs:
                total_tasks = len(latest_project['schedule'])
                completed = sum(1 for log in progress_logs if log['completion'] >= 100)
                overall_progress = (completed / total_tasks * 100) if total_tasks > 0 else 0
            
            student_progress.append({
                'student': student,
                'project': latest_project,
                'progress': overall_progress
            })
        
        feedback_list = list(faculty_feedback_collection.find({'faculty_id': session['user_id']}).sort('created_at', -1))
        
        return render_template('mentoring.html',
                             student_progress=student_progress,
                             feedback_list=feedback_list,
                             role='faculty')
    
    else:
        faculty_members = list(users_collection.find({'role': 'faculty'}))
        
        feedback_received = list(faculty_feedback_collection.find({'student_id': session['user_id']}).sort('created_at', -1))
        
        sessions = list(mentoring_sessions_collection.find({'student_id': session['user_id']}).sort('scheduled_date', -1))
        
        return render_template('mentoring.html',
                             faculty_members=faculty_members,
                             feedback_received=feedback_received,
                             sessions=sessions,
                             role='student')

@app.route('/submit-feedback', methods=['POST'])
@login_required
@faculty_required
def submit_feedback():
    student_id = request.form.get('student_id')
    feedback_text = request.form.get('feedback')
    rating = int(request.form.get('rating', 0))
    
    feedback = {
        'faculty_id': session['user_id'],
        'student_id': student_id,
        'feedback': feedback_text,
        'rating': rating,
        'created_at': datetime.now()
    }
    faculty_feedback_collection.insert_one(feedback)
    
    flash('Feedback submitted successfully!', 'success')
    return redirect(url_for('mentoring'))

@app.route('/schedule-session', methods=['POST'])
@login_required
def schedule_session():
    if session.get('role') == 'student':
        faculty_id = request.form.get('faculty_id')
        session_date = request.form.get('session_date')
        purpose = request.form.get('purpose')
        
        mentoring_session = {
            'student_id': session['user_id'],
            'faculty_id': faculty_id,
            'scheduled_date': datetime.strptime(session_date, '%Y-%m-%d'),
            'purpose': purpose,
            'status': 'pending',
            'created_at': datetime.now()
        }
        mentoring_sessions_collection.insert_one(mentoring_session)
        
        flash('Session scheduled successfully!', 'success')
    
    return redirect(url_for('mentoring'))

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Intelligent Project Scheduling Assistance System")
    print("="*70)
    print("\n📌 Server starting on http://localhost:5006")
    print("📌 MongoDB connection: mongodb://localhost:27017/")
    print("\n✅ All modules initialized:")
    print("   - User Management & Authentication")
    print("   - Skill Requirement Definition")
    print("   - Current Skill Assessment")
    print("   - Rule-Based Skill Gap Analysis")
    print("   - Gap Report Generation")
    print("   - Intelligent Scheduling Engine")
    print("   - Improvement Suggestion System")
    print("   - Progress Tracking & Monitoring")
    print("   - Career Planning & Alignment")
    print("   - Faculty Guidance & Mentoring Portal")
    print("\n" + "="*70 + "\n")
    
    app.run(debug=True, port=5006, host='0.0.0.0')
