# Team Skills Planner V1.0 - Django + MySQL
Enterprise Workforce Planning & Employee Evaluation System built with Django.  
This system is designed to manage employees, roles, skills, projects, training, and performance evaluations in a structured and scalable way.

The project simulates a real-world internal management system used by operations, technical teams, and supervisors to track workforce readiness, staffing, and skill development.

---

## Features

- Employee management
- Role & skill profiles
- Project staffing planning
- Training tracking
- Performance evaluations
- Dashboard with statistics
- Workforce availability tracking
- Admin CRUD portal
- Evaluation scoring system
- Role-based skill requirements
- Drill-down project view
- Seed demo data command

---

## Tech Stack

- Python 3
- Django
- MySQL
- Bootstrap
- HTML / CSS / JS
- Gunicorn (production)
- python-dotenv
- WhiteNoise

---

## Project Structure


config/ → Django settings
planner/ → main app
templates/ → HTML templates
static/ → CSS / JS / images
management/commands/ → seed data
models.py → database models
views.py → logic
forms.py → forms
urls.py → routes


---

## Database Models

- Employee
- RoleProfile
- Skill
- RoleSkill
- Project
- Training
- Evaluation
- EvaluationResult
- Availability

---

## Installation

Clone project


git clone https://github.com/waseemkestenous/Team-Skills-Planner.git

cd Team-Skills-Planner


Create virtual env


python -m venv venv
source venv/bin/activate


Install packages


pip install -r requirements.txt


Create .env


SECRET_KEY=change-me
DEBUG=True

DB_NAME=quanta_planner
DB_USER=root
DB_PASSWORD=1234
DB_HOST=127.0.0.1
DB_PORT=3306


Run migrations


python manage.py migrate


Load demo data


python manage.py seed_quanta


Run server


python manage.py runserver


---

## Production

Run with Gunicorn


gunicorn config.wsgi:application


Collect static


python manage.py collectstatic


---

## Purpose of the Project

This project was built as a real-world simulation of an enterprise workforce planning system similar to those used in large operations environments such as data centers, manufacturing, and technical support organizations.

The goal was to demonstrate:

- Backend architecture design
- Django ORM modeling
- CRUD admin systems
- Evaluation scoring logic
- Dashboard analytics
- Production-ready configuration

---

## Author

Waseem Gerges  
Full Stack & Cloud AI Infrastructure Engineer | Python | Django | React | AWS | Linux | Docker
