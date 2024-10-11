#--depends-on commands
#--depends-on location

from src import EventManager, ModuleManager, utils
import pytz

class Module(ModuleManager.BaseModule):
    def on_load(self):
        pass  # No need to load the location module dynamically
        
    @utils.hook("received.message.channel", priority=EventManager.PRIORITY_HIGH)
    def channel_message(self, event):
        messages = event["channel"].get_user_setting(event["user"].get_id(), "to", [])
        for nickname, message, timestamp in messages:
            timestamp_parsed = utils.datetime.parse.iso8601(timestamp)
            
            # Fetch the recipient's timezone from user settings (set by the location module)
            location_data = event["user"].get_setting("location", None)
            if location_data:
                timezone_name = location_data.get("timezone", "UTC")
                user_tz = pytz.timezone(timezone_name)
            else:
                # Default to UTC if no location is set
                user_tz = pytz.utc

            # Convert the timestamp to the user's timezone
            timestamp_local = timestamp_parsed.astimezone(user_tz)
            timestamp_human = utils.datetime.format.datetime_human(timestamp_local)

            event["channel"].send_message("%s: <%s> %s (at %s %s)" % (
                event["user"].nickname, nickname, message, timestamp_human, user_tz.zone))
        
        if messages:
            event["channel"].del_user_setting(event["user"].get_id(), "to")

    @utils.hook("received.command.to", alias_of="tell")
    @utils.hook("received.command.tell")
    @utils.kwarg("min_args", 2)
    @utils.kwarg("channel_only", True)
    @utils.kwarg("help",
        "Relay a message to a user the next time they talk in this channel")
    @utils.kwarg("usage", "<nickname> <message>")
    def tell(self, event):
        target_name = event["args_split"][0]
        if not event["server"].has_user_id(target_name):
            raise utils.EventError("I've never seen %s before" % target_name)

        target_user = event["server"].get_user(event["args_split"][0])
        messages = event["target"].get_user_setting(target_user.get_id(), "to", [])

        if len(messages) == 5:
            raise utils.EventError("Users can only have 5 messages stored")

        messages.append([event["user"].nickname, " ".join(event["args_split"][1:]), utils.datetime.format.iso8601_now()])
        event["target"].set_user_setting(target_user.get_id(), "to", messages)
        event["stdout"].write("Message saved")
