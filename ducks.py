import random, re, time
import decimal
from src import EventManager, ModuleManager, utils

DUCK_MESSAGES = [
    "・゜゜・。。・゜゜\\_o< QUACK! I'm here!",
    "・゜゜・。。・゜゜\\_o< QUACK! You found me!",
    "・゜゜・。。・゜゜\\_o< QUACK! Catch me if you can!"
]

DEFAULT_MIN_MESSAGES = 50
DUCK_REWARDS = {
    10: "Duck Lover",
    50: "Duck Enthusiast",
    100: "Duck Master",
}

@utils.export("channelset", utils.BoolSetting("ducks-enabled",
    "Whether or not to spawn ducks"))
@utils.export("channelset", utils.IntRangeSetting(50, 200, "ducks-min-messages",
    "Minimum messages between ducks spawning"))
@utils.export("channelset", utils.BoolSetting("ducks-kick",
    "Whether or not to kick someone talking to non-existent ducks"))
@utils.export("channelset", utils.BoolSetting("ducks-prevent-highlight",
    "Whether or not to prevent highlighting users with !friends/!enemies"))
@utils.export("channelset", utils.IntRangeSetting(0, 100, "ducks-fine-percentage", "The fine amount the users get fined when you shoot a duck"))

class Module(ModuleManager.BaseModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duck_hunt_active = False

    @utils.hook("new.channel")
    def new_channel(self, event):
        self.bootstrap_channel(event["channel"])

    def bootstrap_channel(self, channel):
        if not hasattr(channel, "duck_active"):
            channel.duck_active = None
            channel.duck_lines = 0

    def _activity(self, channel):
        self.bootstrap_channel(channel)

        ducks_enabled = channel.get_setting("ducks-enabled", False)

        if (ducks_enabled and not channel.duck_active and not channel.duck_lines == -1):
            channel.duck_lines += 1
            min_lines = channel.get_setting("ducks-min-messages", DEFAULT_MIN_MESSAGES)
            if self.duck_hunt_active:
                min_lines = min_lines // 2  # Ducks appear twice as often during duck hunt

            if channel.duck_lines >= min_lines:
                show_duck = random.SystemRandom().randint(1, 20) == 1

                if show_duck:
                    self._trigger_duck(channel)

    @utils.hook("received.command.duckappear")
    @utils.kwarg("help", "Create ducks")
    @utils.kwarg("permission", "duck")
    def ducks_magic_debug(self, event):
        self._trigger_duck(event["target"])

    @utils.hook("command.regex")
    @utils.kwarg("expect_output", False)
    @utils.kwarg("ignore_action", False)
    @utils.kwarg("command", "duck-trigger")
    @utils.kwarg("pattern", re.compile(".+"))
    def channel_message(self, event):
        self._activity(event["target"])

    def _trigger_duck(self, channel):
        channel.duck_lines = -1
        delay = random.SystemRandom().randint(5, 20)
        self.timers.add("duck", self._send_duck, delay, channel=channel)

    def _send_duck(self, timer):
        channel = timer.kwargs["channel"]
        channel.duck_active = time.time()
        channel.duck_lines = 0
        message = random.choice(DUCK_MESSAGES)
        channel.send_message(message)

    def _total_coins(self, event):
        coins = self.bot.modules.modules['coins'].module
        return decimal.Decimal(sum(coins._all_coins(event['server']).values()))

    @utils.hook("received.command.totalcoins")
    @utils.kwarg("help", "Show total coins")
    def duck_total_coins_amount(self, event):
        event["stdout"].write(f"There are a total of: {self._total_coins(event)} coins")

    def _duck_action(self, channel, user, action, setting, event, fine_enabled=False):
        if channel.get_setting("ducks-fine-percentage", 0) != 0 and fine_enabled:
            coins = self.bot.modules.modules['coins'].module
            interest_percentage = channel.get_setting("ducks-fine-percentage", 1)
            total_coins = self._total_coins(event)
            fine_amount = total_coins * (decimal.Decimal(0.01) * interest_percentage)
            fine_amount = fine_amount.quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_05UP)  # Round number to appropriate units
            user_coins = coins._get_user_coins(user)
            if user_coins < fine_amount:
                return f"There was a duck, but you didn't have coins to pay the fine of {fine_amount} coins so you can't shoot the duck."
            else:
                new_user_coins = user_coins - fine_amount
                coins._set_user_coins(user, new_user_coins)

        duck_timestamp = channel.duck_active
        channel.set_setting("duck-last", time.time())
        channel.duck_active = None

        user_id = user.get_id()
        action_count = channel.get_user_setting(user_id, setting, 0)
        action_count += 1
        channel.set_user_setting(user_id, setting, action_count)

        seconds = round(time.time() - duck_timestamp, 2)

        ducks_plural = "duck" if action_count == 1 else "ducks"

        points = self._award_points(user, 10)
        level_up = self._check_level_up(user, points)

        response = "%s %s a duck in %s seconds! You've %s %d %s in %s!" % (
            user.nickname, action, seconds, action, action_count, ducks_plural,
            channel.name)
        
        if level_up:
            response += f" Congratulations {user.nickname}! You've reached the level: {level_up}"

        return response

    def _no_duck(self, channel, user, stderr):
        message = "There was no duck!"
        duck_timestamp = channel.get_setting("duck-last", None)
        if not duck_timestamp == None:
            seconds = round(time.time() - duck_timestamp, 2)
            message += " missed by %s seconds" % seconds

        if channel.get_setting("ducks-kick"):
            channel.send_kick(user.nickname, message)
        else:
            stderr.write("%s: %s" % (user.nickname, message))

    @utils.hook("received.command.bef", alias_of="befriend")
    @utils.hook("received.command.befriend")
    @utils.kwarg("help", "Befriend a duck")
    @utils.spec("!-channelonly")
    def befriend(self, event):
        if event["target"].duck_active:
            action = self._duck_action(event["target"], event["user"], "befriended", event, "ducks-befriended")
            event["stdout"].write(action)
        else:
            self._no_duck(event["target"], event["user"], event["stderr"])

    @utils.hook("received.command.trap")
    @utils.kwarg("help", "Trap a duck")
    @utils.spec("!-channelonly")
    def trap(self, event):
        if event["target"].duck_active:
            action = self._duck_action(event["target"], event["user"], "trapped", "ducks-shot", event, fine_enabled=True)
            event["stdout"].write(action)
        else:
            self._no_duck(event["target"], event["user"], event["stderr"])

    @utils.hook("received.command.bang")
    @utils.kwarg("help", "Shot a duck")
    @utils.spec("!-channelonly")
    def bang(self, event):
        if event["target"].duck_active:
            action = self._duck_action(event["target"], event["user"], "shot", "ducks-shot", event, fine_enabled=True)
            event["stdout"].write(action)
        else:
            self._no_duck(event["target"], event["user"], event["stderr"])

    def _target(self, target, is_channel, query):
        if query:
            if not query == "*":
                return query
        elif is_channel:
            return target.name

    @utils.hook("received.command.friends")
    @utils.kwarg("help", "Show top 10 duck friends")
    @utils.spec("?<channel>word")
    def friends(self, event):
        query = self._target(event["target"], event["is_channel"], event["spec"][0])
        stats = self._top_duck_stats(event["server"], event["target"], "ducks-befriended", "friends", query)
        event["stdout"].write(stats)

    @utils.hook("received.command.enemies")
    @utils.kwarg("help", "Show top 10 duck enemies")
    @utils.spec("?<channel>word")
    def enemies(self, event):
        query = self._target(event["target"], event["is_channel"], event["spec"][0])
        stats = self._top_duck_stats(event["server"], event["target"], "ducks-shot", "enemies", query)
        event["stdout"].write(stats)

    def _top_duck_stats(self, server, target, setting, description, channel_query):
        channel_query_str = ""
        if not channel_query == None:
            channel_query = server.irc_lower(channel_query)
            channel_query_str = " in %s" % channel_query

        stats = server.find_all_user_channel_settings(setting)

        user_stats = {}
        for channel, nickname, value in stats:
            if not channel_query or channel_query == channel:
                if not nickname in user_stats:
                    user_stats[nickname] = 0
                user_stats[nickname] += value

        top_10 = utils.top_10(user_stats, convert_key=lambda n: self._get_nickname(server, target, n))
        return "Top duck %s%s: %s" % (description, channel_query_str, ", ".join(top_10))

    def _get_nickname(self, server, target, nickname):
        nickname = server.get_user(nickname).nickname
        if target.get_setting("ducks-prevent-highlight", True):
            nickname = utils.prevent_highlight(nickname)
        return nickname

    @utils.hook("received.command.duckstats")
    @utils.kwarg("help", "Get yours, or someone else's, duck stats")
    @utils.spec("?<nickname>ouser")
    def duckstats(self, event):
        target_user = event["spec"][0] or event["user"]

        befs = target_user.get_channel_settings_per_setting("ducks-befriended")
        traps = target_user.get_channel_settings_per_setting("ducks-shot")

        all = [(chan, val, "bef") for chan, val in befs]
        all += [(chan, val, "trap") for chan, val in traps]

        current = {"bef": 0, "trap": 0, "shot": 0}
        overall = {"bef": 0, "trap": 0, "shot": 0}

        if event["is_channel"]:
            for channel_name, value, action in all:
                if not action in overall:
                    overall[action] = 0
                overall[action] += value

                if event["is_channel"]:
                    channel_name_lower = event["server"].irc_lower(channel_name)
                    if channel_name_lower == event["target"].name:
                        current[action] = value

        current_str = ""
        if current:
            current_str = " (%d/%d in %s)" % (current["bef"], current["trap"], event["target"].name)

        event["stdout"].write(
            "%s has befriended %d and shot %d ducks%s" %
            (target_user.nickname, overall["bef"], overall["trap"], current_str))

    @utils.hook("received.command.leaderboard")
    @utils.kwarg("help", "Show duck leaderboard")
    @utils.spec("?<channel>word")
    def leaderboard(self, event):
        query = self._target(event["target"], event["is_channel"], event["spec"][0])
        stats = self._top_duck_stats(event["server"], event["target"], "duck_points", "points", query)
        event["stdout"].write(stats)

    def _award_points(self, user, points):
        current_points = user.get_setting("duck_points", 0)
        new_points = current_points + points
        user.set_setting("duck_points", new_points)
        return new_points

    def _check_level_up(self, user, points):
        for point_threshold, title in DUCK_REWARDS.items():
            if points >= point_threshold and not user.get_setting(f"level_{point_threshold}", False):
                user.set_setting(f"level_{point_threshold}", True)
                return title
        return None

    @utils.hook("received.command.customduck")
    @utils.kwarg("help", "Customize your duck")
    @utils.spec("!<color>word")
    def customduck(self, event):
        color = event["spec"][0]
        user = event["user"]
        user.set_setting("duck_color", color)
        event["stdout"].write(f"Your duck will now be {color}!")

    @utils.hook("received.command.duckhunt")
    @utils.kwarg("help", "Start a duck hunt event")
    @utils.kwarg("permission", "admin")
    def start_duck_hunt(self, event):
        event["target"].send_message("Duck Hunt Event started! Ducks will appear more frequently for the next 5 minutes!")
        self.duck_hunt_active = True
        self.timers.add("duck_hunt_end", self.end_duck_hunt, 300, channel=event["target"])

    def end_duck_hunt(self, timer):
        self.duck_hunt_active = False
        timer.kwargs["channel"].send_message("Duck Hunt Event has ended! Hope you had fun!")
