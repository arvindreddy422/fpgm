# PG Management - Flask Version

A Flask-based web application for managing Paying Guest (PG) accommodations. This application helps PG owners manage rooms, occupants, rent tracking, and bookings.

## Features

- **User Authentication**: Secure registration and login system with bcrypt password hashing
- **Multi-floor Configuration**: Support for multiple floors with customizable room layouts
- **Room Management**: Add, view, and manage rooms across different floors
- **Occupant Management**: Track occupants with join dates, contact information
- **Rent Tracking**: Monthly rent tracking with payment status
- **Advance Bookings**: Manage advance bookings for future occupants
- **Activity History**: Complete audit trail of all activities

## Tech Stack

- **Backend**: Flask (Python web framework)
- **Database**: MongoDB with pymongo
- **Authentication**: Session-based auth with bcrypt
- **Templates**: Jinja2 (Flask's built-in templating)

## Installation

1. **Clone or navigate to the project directory**:
   ```bash
   cd /home/aravind/dev/ak/pgm2/fpgm
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Linux/Mac
   # or
   venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and set your MongoDB URI and SESSION_SECRET
   ```

5. **Ensure MongoDB is running**:
   - Install MongoDB locally or use a cloud instance (MongoDB Atlas)
   - Update `MONGODB_URI` in `.env` with your connection string

## Running the Application

### Development Mode

```bash
flask --app app run --debug
```

The application will be available at `http://localhost:5000`

### Production Mode

```bash
flask --app app run --host=0.0.0.0 --port=5000
```

Or use a production WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Environment Variables

Create a `.env` file with the following variables:

- `MONGODB_URI`: MongoDB connection string (default: `mongodb://localhost:27017`)
- `SESSION_SECRET`: Secret key for session encryption (change in production!)

## Project Structure

```
fpgm/
├── app.py                 # Main Flask application
├── auth.py                # Authentication and session management
├── database.py            # MongoDB connection
├── config.py              # Application configuration
├── activity_log.py        # Activity logging functionality
├── indexes.py             # Database index definitions
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── README.md              # This file
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── main.html
│   ├── config.html
│   ├── rooms.html
│   ├── rent.html
│   ├── advance_booking.html
│   └── history.html
└── static/                # Static files (CSS, JS, images)
```

## Usage

1. **Register a New Account**: Navigate to `/register` and create an account
2. **Configure Your PG**: Set up floors and rooms in the configuration page
3. **Add Occupants**: Add occupants to rooms from the rooms page
4. **Track Rent**: Mark rent as paid/unpaid on a monthly basis
5. **Manage Bookings**: Keep track of advance bookings
6. **View History**: Monitor all activities through the history page

## Database Collections

The application uses the following MongoDB collections:

- `users`: User accounts
- `config`: Building/floor configuration per user
- `rooms`: Room definitions with capacity
- `occupants`: Current occupants with details
- `rentRecords`: Monthly rent tracking
- `advanceBookings`: Advance booking records
- `activityLogs`: Activity history

## Differences from FastAPI Version

This Flask version is functionally identical to the FastAPI version but uses:

- Flask's routing system instead of FastAPI decorators
- Synchronous request handling (no async/await)
- Flask's built-in Jinja2 templating
- Custom authentication decorator instead of FastAPI Depends
- make_response() for cookie management
- Simpler dependency installation (Flask has built-in form handling)

## License

This project is provided as-is for PG management purposes.
