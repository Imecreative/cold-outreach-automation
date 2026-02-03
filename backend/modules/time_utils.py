"""
Time utility module for timezone detection and optimal send time calculation.
"""
from datetime import datetime, time, timedelta, date
import pytz
from typing import Optional, List, Tuple
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from ..config import DEFAULT_SEND_TIMEZONE, OPTIMAL_SEND_HOURS, OPTIMAL_SEND_DAYS


class TimeManager:
    """Manages timezone detection and send time optimization."""
    
    def __init__(self):
        self.geolocator = Nominatim(user_agent="cold_outreach_app")
        self.tf = TimezoneFinder()
        self.default_tz = pytz.timezone(DEFAULT_SEND_TIMEZONE)

    def get_timezone_for_city(self, city: str) -> str:
        """
        Get timezone string for a city name.
        Returns default timezone if not found.
        """
        if not city:
            return DEFAULT_SEND_TIMEZONE
            
        try:
            # Geocode city
            location = self.geolocator.geocode(city)
            if not location:
                return DEFAULT_SEND_TIMEZONE
                
            # Get timezone from coordinates
            tz_str = self.tf.timezone_at(lng=location.longitude, lat=location.latitude)
            return tz_str if tz_str else DEFAULT_SEND_TIMEZONE
            
        except Exception as e:
            print(f"Error getting timezone for {city}: {e}")
            return DEFAULT_SEND_TIMEZONE

    def get_optimal_send_time(self, city: str = None) -> datetime:
        """
        Calculate the next optimal send time.
        Optimal times: Tue-Thu, 10am or 2pm local time.
        """
        tz_str = self.get_timezone_for_city(city)
        local_tz = pytz.timezone(tz_str)
        now_local = datetime.now(local_tz)
        
        # Sort optimal hours and days
        valid_hours = sorted(OPTIMAL_SEND_HOURS)
        valid_days = sorted(OPTIMAL_SEND_DAYS) # 0=Mon, 1=Tue... 6=Sun
        
        # Try to find a time today
        if now_local.weekday() in valid_days:
            for h in valid_hours:
                candidate = now_local.replace(hour=h, minute=0, second=0, microsecond=0)
                if candidate > now_local:
                    return candidate
        
        # Look forward for next days
        current_date = now_local.date()
        for i in range(1, 14): # Look ahead 2 weeks max
            next_date = current_date + timedelta(days=i)
            if next_date.weekday() in valid_days:
                # Found a valid day, use first valid hour
                first_hour = valid_hours[0]
                optimal_time = datetime.combine(next_date, time(hour=first_hour))
                optimal_time = local_tz.localize(optimal_time)
                return optimal_time
                
        # Fallback (shouldn't happen given logic above)
        return now_local + timedelta(hours=24)

    def to_utc(self, dt: datetime) -> datetime:
        """Convert any datetime to UTC."""
        if dt.tzinfo is None:
            dt = self.default_tz.localize(dt)
        return dt.astimezone(pytz.UTC)

# Global instance
time_manager = TimeManager()

def get_lead_timezone(city: str) -> str:
    return time_manager.get_timezone_for_city(city)

def get_next_send_time(city: str = None) -> datetime:
    return time_manager.get_optimal_send_time(city)
