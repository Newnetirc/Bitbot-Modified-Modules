# --depends-on commands

import json
import re
from src import ModuleManager, utils

URL_TRANSLATE   = "http://translate.googleapis.com/translate_a/single"
URL_LANGUAGES   = "https://cloud.google.com/translate/docs/languages"
REGEX_LANGUAGES = re.compile(r"^(\w+)?:(\w+)?\s+", re.I) 
REGEX_TARGET    = re.compile(r"^([a-z]{2,5})\s+", re.I)         


class Module(ModuleManager.BaseModule):
    @utils.hook("received.command.tr", alias_of="translate")
    @utils.hook("received.command.translate")
    @utils.spec("!<phrase>lstring")
    def translate(self, event):
        """
        :help: Translate the given text ­– supports either **src:dst phrase**
               (e.g. `fr:en bonjour`) **dst phrase** (e.g. `es hola`) or just
               `phrase` (auto-detect ➜ English).
        :usage: [.tr|.translate] [src:][dst] <phrase>
        """
        phrase = event["spec"][0].strip()

        # Defaults preserve existing behaviour
        source_language = "auto"
        target_language = "en"

        # Pattern 1 – full "src:dst " prefix
        match = REGEX_LANGUAGES.match(phrase)
        if match:
            if match.group(1):
                source_language = match.group(1)
            if match.group(2):
                target_language = match.group(2)
            phrase = phrase[len(match.group(0)):]  
        else:
            # Pattern 2 – single "dst " prefix
            match = REGEX_TARGET.match(phrase)
            if match:
                target_language = match.group(1)
                phrase = phrase[len(match.group(0)):] 

        if not phrase:
            event["stderr"].write("Nothing to translate.")
            return

        page = utils.http.request(
            URL_TRANSLATE,
            get_params={
                "client": "gtx",
                "dt": "t",
                "q": phrase,
                "sl": source_language,
                "tl": target_language,
            },
        )

        if page and not page.data.startswith(b"[null,null,"):
            data = page.decode("utf8")
            # Google Translate occasionally returns `,,` → patch to valid JSON
            while ",," in data:
                data = data.replace(",,", ",null,").replace("[,", "[null,")
            data_json      = json.loads(data)
            detected_source = data_json[2]
            translated      = data_json[0][0][0]

            event["stdout"].write(
                f"({detected_source} → {target_language.lower()}) {translated}"
            )
        else:
            event["stderr"].write(
                "Failed to translate; check language codes: " + URL_LANGUAGES
            )
