"""Hand-written cue lexicons. Deliberately small and transparent: every score can be
traced back to the words that fired. Covers period/romance revenge drama (this pack)
plus generic microdrama staples (CEO, divorce, pregnancy...) so it is not over-fitted.
Weights are 0..1 contributions, summed and clipped by the scorer."""

# --- words in DIALOGUE that make a line "stop the scroll" ------------------------------
SHOCK_WORDS = {
    # violence / death / threat
    "kill": .5, "killed": .5, "murder": .6, "murderer": .6, "dead": .4, "death": .35, "die": .4,
    "hang": .5, "hanged": .5, "execute": .5, "execution": .5, "gallows": .5, "burn": .4, "blood": .35,
    "poison": .55, "poisoned": .55, "poisoning": .55, "arsenic": .6, "dungeon": .3, "chains": .3,
    "dagger": .4, "sword": .35, "blade": .35, "gun": .4, "knife": .4, "arrest": .4, "arrested": .4,
    "traitor": .55, "treason": .55, "treasonous": .55, "betray": .5, "betrayed": .5, "betrayal": .5,
    "witch": .45, "witchcraft": .5, "guilty": .35, "crime": .3, "thief": .4, "theft": .4,
    "kidnap": .5, "kidnapped": .5, "accident": .3, "hospital": .25,
    # reveals / identity / status
    "duke": .45, "duchess": .4, "heir": .4, "crown": .3, "king": .3, "prince": .3, "noble": .15,
    "secret": .45, "truth": .4, "lied": .45, "lie": .35, "lies": .35, "liar": .45, "fraud": .4,
    "identity": .45, "alive": .45, "survived": .35, "real": .1, "whole time": .3, "all along": .4,
    "impostor": .5, "imposter": .5, "pretend": .3, "disguise": .35, "disguised": .35,
    "pregnant": .55, "baby": .3, "child": .15, "son": .15, "bastard": .5,
    "divorce": .5, "divorced": .5, "annul": .45, "annulled": .45, "invalid": .4, "illegal": .3,
    "ceo": .3, "billionaire": .35, "fired": .4, "bankrupt": .4, "dna": .5, "will": .05, "inheritance": .35,
    # relationship stakes
    "husband": .25, "wife": .25, "marry": .3, "married": .3, "wedding": .25, "fiancé": .3, "fiance": .3,
    "love": .15, "mine": .2, "never": .15, "swear": .3, "vow": .3, "promise": .15,
    "disown": .4, "disowned": .4, "banish": .4, "banished": .4, "exile": .35, "mercy": .3, "beg": .35,
    "pay": .2, "revenge": .5, "vengeance": .5, "avenge": .5, "regret": .3, "forgive": .15,
    "worthless": .35, "plain": .1, "unworthy": .3, "shame": .3, "ashamed": .3, "humiliat": .3,
}

SHOCK_PHRASES = {
    "how dare": .5, "you dare": .5, "you will pay": .55, "get out": .35, "out of my sight": .4,
    "you lied": .5, "i know who": .5, "i am the": .4, "i am your": .45, "who are you": .35,
    "it was you": .55, "it's you": .3, "you did this": .5, "what have you done": .55,
    "you're not": .25, "you are not": .25, "not anymore": .45, "no one will": .3, "over my dead": .5,
    "i'll kill": .6, "i will kill": .6, "i changed my mind": .45, "marrying me": .45,
    "she's gone": .35, "he's gone": .35, "too late": .4, "it's over": .35, "this ends": .4,
    "kneel": .35, "step aside": .3, "arrest him": .4, "arrest her": .4, "seize": .35,
    "my wife": .35, "my husband": .35, "my mother": .15, "your husband": .3,
}

# --- ACTION / CAMERA text cues (physical beats, reveals) --------------------------------
ACTION_HOT = {
    "slap": .7, "slaps": .7, "slapped": .7, "strikes": .55, "struck": .5, "whip": .5, "crop": .35,
    "shoves": .55, "pushes": .35, "hurls": .55, "throws": .45, "flings": .45, "hurled": .5,
    "grabs": .45, "seizes": .45, "drags": .5, "dragged": .5, "pins": .4, "chokes": .6, "grips": .3,
    "draws a": .45, "unsheathes": .5, "dagger": .4, "sword": .35, "blade": .35, "pistol": .4,
    "collapses": .5, "falls": .25, "faints": .5, "kneels": .35, "drops to": .35, "crawls": .45,
    "shatters": .5, "explosion": .7, "explodes": .7, "bursts": .55, "kicks": .5, "slams": .5,
    "tears": .25, "rips": .45, "blood": .45, "bleeding": .4, "wound": .3, "scream": .5, "screams": .5,
    "gasps": .35, "gasp": .35, "stunned": .35, "shock": .35, "horror": .45, "freezes": .4,
    "unmasks": .5, "reveals": .45, "removes his": .25, "pulls off": .35, "signet": .2, "ring": .1,
    "poison": .45, "arsenic": .45, "chains": .3, "shackle": .35, "ablaze": .5, "flames": .35, "fire": .3,
    "salute": .35, "rips open": .45, "smash": .45, "thud": .35, "crash": .45, "slamming": .4,
    "extreme close-up": .15, "rapid": .1,
}

# --- cliffhanger cues in final beats -------------------------------------------------------
CLIFF_CUES = {
    "cliffhanger": .6, "freeze-frame": .55, "freeze frame": .55, "freezes": .35, "cut to black": .3,
    "smash cut": .5, "sting": .4, "ominous": .4, "dread": .45, "sinister": .4, "menacing": .4,
    "stunned": .35, "shock": .35, "horror": .4, "eyes widen": .4, "widening": .3, "gasp": .35,
    "realiz": .35, "paralyz": .45, "terror": .4, "panic": .35, "trembl": .2, "unseen": .4,
    "shadow": .3, "looming": .35, "footsteps": .3, "door": .15, "bursts": .45, "enters": .2,
    "arrives": .2, "steps in": .25, "appears": .25, "holds on": .2, "hangs": .25, "lingers": .1,
    "triumph": .15, "grin": .25, "smirk": .3, "silence": .2, "dagger": .3, "blade": .3, "pendant": .05,
}
CLIFF_LINE_CUES = {
    "?": .3, "...": .25, "—": .25, "--": .25, "!": .12,
    "who": .2, "what have": .4, "what do you mean": .3, "you...": .2, "can't be": .35, "impossible": .35,
    "you're": .1, "it was you": .45, "i know": .25, "tomorrow": .1, "tonight": .1,
}
RESOLVED_CUES = {
    "smiles warmly": .5, "gentle smile": .4, "soft smile": .35, "warm": .25, "peaceful": .4, "serene": .4,
    "tender": .3, "embrace": .3, "embraces": .3, "kiss": .3, "relieved": .35, "relief": .3, "laughs": .3,
    "fades gently": .45, "fade out": .15, "fades out": .15, "slow fade": .15, "gratitude": .3, "grateful": .3,
    "contentment": .4, "content": .15, "radiant": .15, "triumphant": .1, "melancholic": .1, "sleep": .2,
    "rest": .05, "thank you": .25, "i love you": .3, "safe now": .4, "it is over": .3, "settles": .2,
}

# --- clarity cues -----------------------------------------------------------------------
RELATION_WORDS = {
    "husband", "wife", "mother", "father", "sister", "brother", "fiancé", "fiance", "daughter", "son",
    "duke", "duchess", "lord", "lady", "stepmother", "marriage", "married", "wedding", "king", "queen",
    "master", "servant", "maid", "boss", "ceo", "heir", "betrothed", "bride", "groom",
}
PRONOUN_OPEN = {"he", "she", "they", "it", "that", "this", "those", "these", "him", "her", "them", "and", "but",
                "so", "then", "because", "or", "yet"}
RESPONSE_OPEN = {"yes", "no", "indeed", "very", "fine", "well", "perhaps", "maybe", "i see", "understood",
                 "of course", "alright", "all right", "thank", "thanks", "sorry", "please", "hm", "mm"}
GREETING = ("good morning", "good evening", "good afternoon", "welcome", "hello", "greetings", "my lady",
            "my lord", "your grace")
TONE_HOT = {
    "shout": .5, "scream": .5, "furious": .5, "fury": .5, "rage": .5, "enraged": .5, "outrag": .45,
    "cold": .25, "icy": .35, "menac": .45, "threat": .45, "venom": .45, "seething": .4, "snarl": .4,
    "cruel": .3, "sadistic": .45, "gloating": .35, "mocking": .3, "sneer": .3, "contempt": .3, "scornful": .3,
    "desperate": .35, "pleading": .3, "sobbing": .3, "crying": .25, "gasp": .3, "stunned": .3, "horrified": .4,
    "trembling": .15, "whisper": .1, "panic": .35, "defiant": .3, "fierce": .35, "ferocious": .4, "commanding": .3,
    "booming": .4, "thunder": .4, "low growl": .4, "deadly": .45, "lethal": .45, "triumphant": .2,
}
