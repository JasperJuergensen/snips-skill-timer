#!/usr/bin/env python3
# coding: utf-8

from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions

from datetime import timedelta
import time
from threading import Thread, Event

import toml


MQTT_BROKER_ADDRESS = "localhost:1883"
MQTT_USERNAME = None
MQTT_PASSWORD = None

# get snips config
snips_config = toml.load('/etc/snips.toml')
if 'mqtt' in snips_config['snips-common'].keys():
    MQTT_BROKER_ADDRESS = snips_config['snips-common']['mqtt']
if 'mqtt_username' in snips_config['snips-common'].keys():
    MQTT_USERNAME = snips_config['snips-common']['mqtt_username']
if 'mqtt_password' in snips_config['snips-common'].keys():
    MQTT_PASSWORD = snips_config['snips-common']['mqtt_password']

TIMER_LIST = []


class TimerBase(Thread):
    """
    """
    def __init__(self, hermes, intentMessage):

        super(TimerBase, self).__init__()

        self._start_time = 0
        
        self.hermes = hermes
        self.session_id = intentMessage.session_id
        self.site_id = intentMessage.site_id
        
        if intentMessage.slots.duration:
            duration = intentMessage.slots.duration.first()
            self.durationRaw = self.get_duration_raw(duration)
        
            self.wait_seconds = self.get_seconds_from_duration(duration)
        else:
            text_now = u"Ich habe die angegebene Dauer nicht verstanden."
            hermes.publish_end_session(intentMessage.session_id, text_now)
            raise Exception('Timer need dutration')
            
        if intentMessage.slots.sentence:
            self.sentence = intentMessage.slots.sentence.first().rawValue
        else:
            self.sentence = None

        TIMER_LIST.append(self)
        self.event = Event()
        self.event.clear()

        self.send_text_started()

    @staticmethod
    def get_seconds_from_duration(duration):
    
        days = duration.days
        hours = duration.hours
        minutes = duration.minutes
        seconds = duration.seconds
        return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds()
    
    @staticmethod
    def get_duration_raw(duration):

        result = ''
        
        days = duration.days
        hours = duration.hours
        minutes = duration.minutes
        seconds = duration.seconds
        
        length = 0
        
        if seconds > 0:        
            result = '{} Sekunden'.format(str(seconds))
            length += 1
        if minutes > 0:
            if length > 0:
                add_and = ' und '
            else: 
                add_and = ''
            result = '{} Minuten{}{}'.format(str(minutes), add_and, result)
            length += 1
        if hours > 0:
            if length > 1:
                add_and = ', '
            elif length > 0:
                add_and = ' und '
            else: 
                add_and = ''
            result = '{} Stunden{}{}'.format(str(hours), add_and, result)
            length += 1
        if days > 0:
            if length > 1:
                add_and = ', '
            elif length > 0:
                add_and = ' und '
            else: 
                add_and = ''
            result = '{} Tage{}{}'.format(str(days), add_and, result)
        return result

    @property
    def remaining_time(self):
        if self._start_time == 0:
            return 0
        return int((self._start_time + self.wait_seconds) - time.time())

    @property
    def remaining_time_str(self):        
        seconds = self.remaining_time

        if seconds == 0:
            return None

        result = ''
        add_and = ''
        t = str(timedelta(seconds=seconds)).split(':')
        
        if int(t[2]) > 0:
            add_and = ' und '
            result += "{} Sekunden".format(int(t[2]))
        
        if int(t[1]) > 0:         
            result = "{} Minuten {}{}".format(int(t[1]), add_and, result)
            if add_and != '':
                add_and = ', '
            else:
                add_and = ' und '
        
        if int(t[0]) > 0:
            
            result = "{} Stunden{}{}".format(int(t[0]), add_and, result)
        return result

    def run(self):

        print("[{}] Start timer: wait {} seconds".format(time.time(), self.wait_seconds))
        self.event.clear()
        self._start_time = time.time()
        if not self.event.wait(self.wait_seconds):  # If true, the timer has been killed
            self.__callback()

    def __callback(self):
        print("[{}] End timer: wait {} seconds".format(time.time(), self.wait_seconds))
        TIMER_LIST.remove(self)
        self.callback()

    def callback(self):
        raise NotImplementedError('You should implement your callback')

    def send_text_started(self):
        text_now = u"Der Teimer {} wurde gestartet.".format(str(self.durationRaw))
        self.hermes.publish_end_session(self.session_id, text_now)


class SimpleTimer(TimerBase):

    def callback(self):
        text = u"Der Teimer mit {} ist abgelaufen.".format(str(self.durationRaw))
        self.hermes.publish_start_session_notification(site_id=self.site_id, session_initiation_text=text,
                                                       custom_data=None)

                
class TimerSendNotification(TimerBase):

    def callback(self):
        if self.sentence is None:
            text = u"Der Teimer mit {} ist abgelaufen.".format(str(self.durationRaw))
        else:
            text = u"Le minuteur de {} vient de ce terminer je doit vous rappeler de {}".format(
                self.durationRaw, self.sentence)
        
        self.hermes.publish_start_session_notification(site_id=self.site_id, session_initiation_text=text,
                                                       custom_data=None)


class TimerSendAction(TimerBase):

    def callback(self):        
        self.hermes.publish_start_session_action(site_id=self.site_id, session_init_text=self.sentence,
                                                 session_init_intent_filter=[],
                                                 session_init_can_be_enqueued=False, custom_data=None)


def simpleTimer(hermes, intentMessage):

    timer = SimpleTimer(hermes, intentMessage)
    timer.start()


def timerRemember(hermes, intentMessage):
    
    timer = TimerSendNotification(hermes, intentMessage)
    timer.start()
        
        
def timerAction(hermes, intentMessage):

    # Example in 15 minutes start the TV
    timer = TimerSendAction(hermes, intentMessage)
    timer.start()


def timerRemainingTime(hermes, intentMessage):
    len_timer_list = len(TIMER_LIST)
    if len_timer_list < 1:
        hermes.publish_end_session(intentMessage.session_id, "Es läuft aktuell kein Teimer.")
    else:
        text = u''
        for i, timer in enumerate(TIMER_LIST):            
            text += u"Für den Teimer {} beträgt die Restzeit {}".format(i + 1, timer.remaining_time_str)
            if len_timer_list <= i:
                text += u", "
        hermes.publish_end_session(intentMessage.session_id, text)


def timerList(hermes, intentMessage):
    len_timer_list = len(TIMER_LIST)
    if len_timer_list < 1:
        hermes.publish_end_session(intentMessage.session_id, "Es läuft aktuell kein Teimer.")
    else:
        text = u'Es laufen aktuell die folgenden Teimer:'
        for i, timer in enumerate(TIMER_LIST): 
            text += u'Teimer {} mit {}'.format(i + 1, str(timer.durationRaw))
            if len_timer_list <= i:
                text += u', '
        hermes.publish_end_session(intentMessage.session_id, text)


def timerRemove(hermes, intentMessage):
    if len(TIMER_LIST) < 1:
        hermes.publish_end_session(intentMessage.session_id, 'Es laufen aktuell keine Teimer.')
        return
    if intentMessage.slots.timer_id:
        try:
            timer_id = int(intentMessage.slots.timer_id.first().value) - 1
        except ValueError:
            hermes.publish_end_session(intentMessage.session_id, 'Die Timer ID konnte nicht verstanden werden.')
            return
        if timer_id > len(TIMER_LIST) - 1:
            hermes.publish_end_session(intentMessage.session_id, 'Der angegebene Teimer existiert nicht.')
            return
        removed_timer = TIMER_LIST.pop(timer_id)
        removed_timer.event.set()
        text = 'Der Teimer {} wurde gestoppt.'.format(timer_id)
    elif len(TIMER_LIST) == 1:
        removed_timer = TIMER_LIST.pop(0)
        removed_timer.event.set()
        text = 'Der Teimer wurde gestoppt.'
    else:
        #hermes.publish_continue_session(intentMessage.session_id, 'Welchen Teimer möchtests du beenden?')
        #return
        text = 'Ich weiß leider nicht, welchen Teimer ich beenden soll.'
    hermes.publish_end_session(intentMessage.session_id, text)


if __name__ == "__main__":  

    mqtt_opts = MqttOptions(username=MQTT_USERNAME, password=MQTT_PASSWORD, broker_address=MQTT_BROKER_ADDRESS)  

    with Hermes(mqtt_options=mqtt_opts) as h:
        h.subscribe_intent("JasperJuergensen:StartTimer", simpleTimer).subscribe_intent("JasperJuergensen:StopTimer", timerRemove).loop_forever()
