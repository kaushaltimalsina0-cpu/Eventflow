# EventFlow — Event Management System

Functional Flask + SQLite event-management MVP for a local Windows demo.

## Included
- Login with Admin and Team Member demo accounts
- Dashboard with live event/task/material statistics and alerts
- Event create/edit/delete, search and status filtering
- Event workspace: Overview, Team, Tasks, Materials, Vendors/Budget, Activity
- Team member add/edit/delete
- Task add/edit/delete, assignment, priority, due date and status
- Event progress automatically calculated from completed tasks
- Material quantity tracking with automatic Available / Shortage / Out of Stock status
- Vendor estimated/actual costs and payment status
- Global Team, Tasks, Materials, Vendors and Activity pages with search/filtering
- SQLite persistence and realistic College Fest demo data

## Run
Double-click START_EVENTFLOW.bat, then open http://127.0.0.1:5000

Admin: admin@example.com / admin123
Team member: member@example.com / member123

## Prototype limitation
This is a local student prototype. Passwords are stored plainly and Flask's development server is used. Add secure password hashing, CSRF protection, and a production WSGI server before real deployment.


## Important: real-data mode
This version starts with an empty event list. Demo data is NOT inserted automatically. Use **Events → Load demo data** only when you deliberately want sample data.

### Editing and deleting
The Events page now has **Open / Edit / Delete** on every event card. Event details also have Edit/Delete. Team, tasks, materials, and vendors have their own edit/delete controls.

### Time tracking
Each task has a **Start timer / Pause** control. Tracked time is stored in SQLite and survives page refreshes. Completing a task stops its timer and preserves the recorded time.
