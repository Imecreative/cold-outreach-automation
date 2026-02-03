"""
Email Scheduler Module
Uses APScheduler for timing and JSON for persistence.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError

from ..models import SequenceStep
from ..config import SCHEDULER_PERSISTENCE_FILE
from ..modules.excel_handler import get_handler
from ..modules.gmail_sender import send_email

# Set up logging
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.WARNING)

class EmailScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.persistence_file = Path(SCHEDULER_PERSISTENCE_FILE)
        self.jobs_metadata = self._load_jobs_metadata()
        
    def start(self):
        """Start the scheduler and restore jobs."""
        if not self.scheduler.running:
            self.scheduler.start()
            self._restore_jobs()
            print("Scheduler started and jobs restored.")

    def shutdown(self):
        """Shutdown scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _load_jobs_metadata(self) -> Dict[str, Any]:
        """Load jobs metadata from JSON file."""
        if self.persistence_file.exists():
            try:
                with open(self.persistence_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading scheduler persistence file: {e}")
                return {}
        return {}

    def _save_jobs_metadata(self):
        """Save jobs metadata to JSON file."""
        try:
            with open(self.persistence_file, 'w') as f:
                json.dump(self.jobs_metadata, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving scheduler persistence file: {e}")

    def _restore_jobs(self):
        """Restore jobs from metadata on startup."""
        for lead_id_str, job_data in self.jobs_metadata.items():
            lead_id = int(lead_id_str)
            run_date_str = job_data['run_date']
            
            try:
                run_date = datetime.fromisoformat(run_date_str)
                # Only reschedule if in future
                if run_date > datetime.now(run_date.tzinfo):
                    self.scheduler.add_job(
                        self._execute_email_send,
                        'date',
                        run_date=run_date,
                        args=[lead_id, job_data['subject'], job_data['body']],
                        id=str(lead_id),
                        replace_existing=True
                    )
                else:
                    # Job execution missed, handled by cleanup or manual review
                    print(f"Skipping past job for lead {lead_id} at {run_date}")
            except Exception as e:
                print(f"Failed to restore job for lead {lead_id}: {e}")

    def schedule_email(self, lead_id: int, subject: str, body: str, run_date: datetime) -> str:
        """
        Schedule an email to be sent.
        Returns job_id (which is str(lead_id)).
        """
        job_id = str(lead_id)
        
        # Add to APScheduler
        self.scheduler.add_job(
            self._execute_email_send,
            'date',
            run_date=run_date,
            args=[lead_id, subject, body],
            id=job_id,
            replace_existing=True
        )
        
        # Save to persistence
        self.jobs_metadata[job_id] = {
            "lead_id": lead_id,
            "subject": subject,
            "body": body,
            "run_date": run_date.isoformat(),
            "created_at": datetime.now().isoformat()
        }
        self._save_jobs_metadata()
        
        return job_id

    def cancel_email(self, lead_id: int) -> bool:
        """Cancel a scheduled email."""
        job_id = str(lead_id)
        
        try:
            self.scheduler.remove_job(job_id)
        except JobLookupError:
            pass # Job might not exist in scheduler but exists in metadata
            
        if job_id in self.jobs_metadata:
            del self.jobs_metadata[job_id]
            self._save_jobs_metadata()
            return True
        return False

    def get_scheduled_job(self, lead_id: int) -> Dict[str, Any]:
        """Get details of a scheduled job."""
        return self.jobs_metadata.get(str(lead_id))

    def _execute_email_send(self, lead_id: int, subject: str, body: str):
        """
        Internal function executed by scheduler to send email and update DB.
        """
        print(f"Executing scheduled send for lead {lead_id}")
        
        # Remove from persistence first (so we don't retry if it crashes mid-send, or handle safer?)
        # Better to keep until confirmed, but for now simple removal
        job_id = str(lead_id)
        if job_id in self.jobs_metadata:
            del self.jobs_metadata[job_id]
            self._save_jobs_metadata()
            
        # Get handler
        handler = get_handler()
        if not handler:
            print("Error: No Excel handler available for scheduled send")
            return

        lead = handler.get_lead(lead_id)
        if not lead:
            print(f"Error: Lead {lead_id} not found")
            return
            
        if not lead.email:
            print(f"Error: Lead {lead_id} has no email")
            return

        # Send Email using sync context if needed or run async
        # Since APScheduler runs in thread, we can call async code via asyncio.run or use sync version
        # The send_email function from gmail_sender is async.
        # We need to run it synchronously here.
        import asyncio
        
        try:
            success, message = asyncio.run(send_email(lead.email, subject, body))
        except Exception as e:
            print(f"Error sending email in scheduler: {e}")
            success = False
            message = str(e)
            
        if success:
            # Update Lead
            new_step = SequenceStep.INITIAL_SENT
            if lead.sequence_step == SequenceStep.INITIAL_SENT:
                new_step = SequenceStep.GHOST_1_SENT
            elif lead.sequence_step == SequenceStep.GHOST_1_SENT:
                new_step = SequenceStep.GHOST_2_SENT
                
            handler.update_lead(lead_id, {
                "email_sent_at": datetime.now(),
                "sequence_step": new_step,
                "email_subject": subject,
                "email_draft": body,
                "scheduled_at": None # Clear scheduled flag
            })
            handler.save()
            print(f"Successfully sent scheduled email to {lead.email}")
        else:
            print(f"Failed to send scheduled email to {lead.email}: {message}")

# Global instance
email_scheduler = EmailScheduler()
