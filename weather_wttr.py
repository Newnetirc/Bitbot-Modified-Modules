#--depends-on commands
#--depends-on location
#--Untested code

from src import ModuleManager, utils

WTTR_URL = "http://wttr.in"

class Module(ModuleManager.BaseModule):
    def _user_location(self, user):
        user_location = user.get_setting("location", None)
        if user_location:
            name = user_location.get("name", None)
            return [user_location["lat"], user_location["lon"], name]

    @utils.hook("received.command.w", alias_of="weather")
    @utils.hook("received.command.weather")
    def weather(self, event):
        """
        :help: Get current weather for you or someone else
        :usage: [nickname]
        :require_setting: location
        :require_setting_unless: 1
        """
        location = None
        query = None
        nickname = None
        
        if event["args"]:
            query = event["args"]
            if len(event["args_split"]) == 1 and event["server"].has_user_id(event["args_split"][0]):
                target_user = event["server"].get_user(event["args_split"][0])
                location = self._user_location(target_user)
                if location:
                    nickname = target_user.nickname
        else:
            location = self._user_location(event["user"])
            nickname = event["user"].nickname
            if not location:
                raise utils.EventError("You don't have a location set")

        if not location and query:
            location_info = self.exports.get("get-location")(query)
            if location_info:
                location = [location_info["lat"], location_info["lon"], location_info.get("name", None)]
        if not location:
            raise utils.EventError("Unknown location")

        lat, lon, location_name = location
        location_str = f"{lat},{lon}"
        
        # Requesting weather data from wttr.in
        weather_url = f"{WTTR_URL}/{location_str}?format=3"
        response = utils.http.request(weather_url).text.strip()
        
        if not response:
            raise utils.EventResultsError("Failed to fetch weather data")

        # Formatting the output for the IRC bot
        if nickname:
            response = f"({nickname}) {response}"
        
        event["stdout"].write(response)
