#!/usr/bin/env python3
# coding: utf-8

from hermes_python.hermes import Hermes
from datetime import timedelta
import time
from threading import Thread


MQTT_IP_ADDR = "localhost"
MQTT_PORT = 1883
MQTT_ADDR = "{}:{}".format(MQTT_IP_ADDR, str(MQTT_PORT))

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

        self.send_end()

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
        self._start_time = time.time()
        time.sleep(self.wait_seconds)
        self.__callback()

    def __callback(self):
        print("[{}] End timer: wait {} seconds".format(time.time(), self.wait_seconds))
        TIMER_LIST.remove(self)
        self.callback()

    def callback(self):
        raise NotImplementedError('You should implement your callback')

    def send_end(self):
        raise NotImplementedError('You should implement your send end')

                
class TimerSendNotification(TimerBase):

    def callback(self):
        if self.sentence is None:
            text = u"Der Timer mit {} ist abgelaufen.".format(str(self.durationRaw))
        else:
            text = u"Le minuteur de {} vient de ce terminer je doit vous rappeler de {}".format(
                self.durationRaw, self.sentence)
        
        self.hermes.publish_start_session_notification(site_id=self.site_id, session_initiation_text=text,
                                                       custom_data=None)

    def send_end(self):
        if self.sentence is None:
            text_now = u"Der Timer {} ist abgelaufen.".format(str(self.durationRaw))
        else:
            text_now = u"Je vous rappelerais dans {} de {}".format(str(self.durationRaw), str(self.sentence))
        
        self.hermes.publish_end_session(self.session_id, text_now)


class TimerSendAction(TimerBase):

    def callback(self):        
        self.hermes.publish_start_session_action(site_id=self.site_id, session_init_text=self.sentence,
                                                 session_init_intent_filter=[],
                                                 session_init_can_be_enqueued=False, custom_data=None)

    def send_end(self):
        if self.sentence is None:
            raise Exception('TimerSendAction need sentence with action')
        text_now = u"Dans {} je ferais l'action: {}".format(str(self.durationRaw), str(self.sentence))
        self.hermes.publish_end_session(self.session_id, text_now)


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
        hermes.publish_end_session(intentMessage.session_id, "Es läuft aktuell kein Timer.")
    else:
        text = u''
        for i, timer in enumerate(TIMER_LIST):            
            text += u"Für den Timer {} beträgt die Restzeit {}".format(i + 1, timer.remaining_time_str)
            if len_timer_list <= i:
                text += u", "
        hermes.publish_end_session(intentMessage.session_id, text)


def timerList(hermes, intentMessage):
    pass


def timerRemove(hermes, intentMessage):
    pass


if __name__ == "__main__":    

    with Hermes(MQTT_ADDR) as h:
        h.subscribe_intent("JasperJuergensen:StartTimer", timerRemember).subscribe_intent("JasperJuergensen:RemainingTime", timerRemainingTime).loop_forever()
