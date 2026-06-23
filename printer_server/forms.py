"""User forms."""
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, BooleanField, SelectField, FormField, FieldList, HiddenField, TextAreaField

# from wtforms import FileField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from printer_server.models import User, PrintRecord

import logging

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class RegisterForm(FlaskForm):
    """Register form."""

    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField(
        "Email", validators=[DataRequired(), Email(), Length(min=6, max=40)]
    )
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=6, max=40)]
    )
    confirm = PasswordField(
        "Verify password",
        [DataRequired(), EqualTo("password", message="Passwords must match")],
    )

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(RegisterForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self):
        """Validate the form."""
        initial_validation = super(RegisterForm, self).validate()
        if not initial_validation:
            return False
        user = User.query.filter_by(username=self.username.data).first()
        if user:
            self.username.errors.append("Username already registered")
            return False
        user = User.query.filter_by(email=self.email.data).first()
        if user:
            self.email.errors.append("Email already registered")
            return False
        return True
    
class StartSessionForm(FlaskForm):
    """Login form"""

    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=6, max=40)]
    )

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(StartSessionForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self):
        """Validate the form."""
        initial_validation = super(StartSessionForm, self).validate()
        if not initial_validation:
            return False
        user = User.query.filter_by(username=self.username.data).first()
        if not user:
            self.username.errors.append("Unknown username")
            return False
        if not user.check_password(self.password.data):
            self.password.errors.append("Invalid password")
            return False
        self.user = user
        return True
    


class EndPrintForm(FlaskForm):
    class Meta:
        csrf = False

    print_id = HiddenField("Print ID")
    print_name = HiddenField("Print Name")
    start_time = HiddenField("Start Time")
    end_time = HiddenField("End Time")
    incomplete = HiddenField("Incomplete")
    print_success = SelectField("Print Succeeded?", choices=[
        ("", "-- Select --"), 
        ("yes", "Yes"), 
        ("no", "No")
    ])
    choices = [
        ("", "-- Select --")
    ] + [
        (e.name, e.value)
        for e in PrintRecord.FailureModeEnum
        if e != PrintRecord.FailureModeEnum.NO_FAILURE
    ]
    failure_mode = SelectField("Failure Mode", choices=choices)
    failure_detail = TextAreaField("Failure Details")
    print_notes = TextAreaField("Print Notes")

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(EndPrintForm, self).__init__(*args, **kwargs)

    def validate(self):
        """Validate the form."""
        failed = False

        initial_validation = super(EndPrintForm, self).validate()
        if not initial_validation:
            failed = True
        
        # If print_success "", show an error
        if self.print_success.data == "":
            self.print_success.errors.append("Please select an option.")
            failed = True

        # If print_success is False, failure_mode must be selected
        if self.print_success.data == "no" and not self.failure_mode.data:
            self.failure_mode.errors.append("Failure mode is required when print is unsuccessful.")
            failed = True

        # If failure_mode is other, failure_detail must be populated
        if self.failure_mode.data == "other" and not self.failure_detail.data:
            self.failure_detail.errors.append("Failure details are required when failure mode is other.")
            failed = True

        return not failed

class EndSessionForm(FlaskForm):

    film_changed = BooleanField("Film Changed")
    printer_issues = BooleanField("Printer Hardware Issues")
    printer_issue_details = TextAreaField("Printer Issue Details")
    session_notes = TextAreaField("Session Notes")

    prints = FieldList(FormField(EndPrintForm), min_entries=0)

    def __init__(self, *args, **kwargs):
        """Create instance."""
        super(EndSessionForm, self).__init__(*args, **kwargs)

    def clear_prints(self):
        """Clear all print entries."""
        for _ in range(len(self.prints)):
            self.prints.pop_entry()

    def validate(self):
        """Validate the form."""
        failed = False

        initial_validation = super(EndSessionForm, self).validate()
        if not initial_validation:
            failed = True
        
        # If printer_issues is checked, printer_issue_details must be populated
        if self.printer_issues.data and not self.printer_issue_details.data:
            self.printer_issue_details.errors.append("Printer issue details are required when printer issues is checked.")
            failed = True
        
        # Validate each print in the session
        for print_form in self.prints:
            if not print_form.validate(print_form):
                failed = True

        return not failed