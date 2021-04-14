#!/usr/bin/env python3

import scheduler_config

import requests
import pickle
import base64
import random
import string
import json
import time
from requests_toolbelt import MultipartEncoder


class Session:
	def __init__(self, username, password, user_id, LOGIN=True, \
			URL_BASE=scheduler_config.URL_BASE):
		self._URL_BASE = URL_BASE
		self._user = username
		self._pass = password
		self._user_id = user_id
		self._CSRF_TOKEN = ""
		self._session = requests.Session()
		self._last_response = None
		self._session.headers.update({
			"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
			"accept-language": "en-US,en;q=0.9,he;q=0.8",
			"cache-control": "max-age=0",
			"content-type": "application/x-www-form-urlencoded",
			"sec-ch-ua": "\"Chromium\";v=\"88\", \"Google Chrome\";v=\"88\", \";Not A Brand\";v=\"99\"",
			"sec-ch-ua-mobile": "?0",
			"sec-fetch-dest": "document",
			"sec-fetch-mode": "navigate",
			"sec-fetch-site": "same-origin",
			"sec-fetch-user": "?1",
			"upgrade-insecure-requests": "1",
			"referrerPolicy": "strict-origin-when-cross-origin"
		})
		if LOGIN: self.login()
		self._LOGIN = LOGIN

	def login(self):
		URL = self._URL_BASE + "/Web/index.php"
		self._session.headers.update({
			"referrer": self._URL_BASE + "/Web/index.php?redirect="
		})
		body = {
			"email":self._user,
			"password":self._pass,
			"captcha":"",
			"login":"submit",
			"resume":"",
			"language":"en_US"
		}
		print("===LOGIN===")
		r = self._session.post(URL, data=body)
		self._last_response = r
		csrf_parts = r.text.split("name=\"CSRF_TOKEN\" value=\"")
		if len(csrf_parts) < 2: return False
		self._CSRF_TOKEN = csrf_parts[1].split("\"")[0]

		URL = self._URL_BASE + "/Web/reservation.php"
		r = self._session.post(URL)
		userid_parts = r.text.split("id=\"userName\" data-userid=\"")
		if len(userid_parts) < 2: return False
		self._user_id = userid_parts[1].split("\"")[0]
		print("User id reveieved: " + str(self._user_id))
		return True
		
	def view_reservations(self, date):
		beginDate = date
		endDate = date
		URL = self._URL_BASE + "/Web/schedule.php?dr=reservations"
		self._session.headers.update({
			"referrer": self._URL_BASE + "/Web/schedule.php"
		})
		body = {
			"beginDate": beginDate, \
			"endDate": endDate, \
			"scheduleId": "3", \
			"MIN_CAPACITY": "", \
			"RESOURCE_TYPE_ID": "", \
			"CSRF_TOKEN": self._CSRF_TOKEN
		}
		r = self._session.post(URL, data=body)
		r = json.loads(r.text)
		reservations = {}
		for booking in r:
			new_booking = {'owner': booking['IsOwner'], 'assigned_id':booking['Id'],'reference':booking['ReferenceNumber'], \
				'resource':booking['ResourceId'], 'hour_start':int(booking['StartTime'].split(":")[0]),'hour_end':int(booking['EndTime'].split(":")[0])}
			reservations[booking['ReferenceNumber']]=new_booking
		return reservations

	def _reservation_post(self, date, hour_start, hour_end, roomId, action, assigned_id="", reference=""):
		URL = fself._URL_BASE + "/Web/ajax/reservation_{action}.php"
		hour_start = ("" if hour_start>=10 else "0")+ str(hour_start) + ":00:00"
		hour_end   = ("" if hour_end>=10 else "0")  + str(hour_end)   + ":00:00"
		plaster = {
			"userId": (None, self._user_id),
			"beginDate": (None, date),
			"beginPeriod": (None, hour_start),
			"endDate": (None, date),
			"endPeriod": (None, hour_end),
			"scheduleId": (None, "3"),
			"resourceId": (None, roomId),
			"reservationTitle": (None, ""),
			"reservationDescription": (None, ""),
			"reservationId": (None, assigned_id),
			"referenceNumber": (None, reference),
			"reservationAction": (None, action),
			"DELETE_REASON": (None, ""),
			"seriesUpdateScope": (None, "full"),
			"CSRF_TOKEN": (None, self._CSRF_TOKEN)
		}
		boundary = '----WebKitFormBoundary' \
			+ ''.join(random.sample(string.ascii_letters + string.digits, 16))
		self._session.headers = {
			'Connection': 'keep-alive',
			'sec-ch-ua': '"Chromium";v="88", "Google Chrome";v="88", ";Not A Brand";v="99"',
			'Accept': '*/*',
			'X-Requested-With': 'XMLHttpRequest',
			'sec-ch-ua-mobile': '?0',
			'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.182 Safari/537.36',
			'Content-Type': 'multipart/form-data; boundary='+boundary,
			'Origin': ('/'.join((self._URL_BASE.split("/"))[:3]))+'/',
			'Sec-Fetch-Site': 'same-origin',
			'Sec-Fetch-Mode': 'cors',
			'Sec-Fetch-Dest': 'empty',
			'Referer': self._URL_BASE + "/Web/reservation.php?rid="+roomId+"&sid="+plaster['scheduleId'][1]+"&rd="+date+"&sd="+date+" "+hour_start+"&ed="+date+" "+hour_end,
			'Accept-Language': 'en-US,en;q=0.9,he;q=0.8'
		}
		m = MultipartEncoder(fields=plaster, boundary=boundary)
		r = self._session.post(URL, data=m, headers=self._session.headers, cookies=self._session.cookies)
		print(f"==={action}===\n{r.text}")
		self._last_response = r
		if "reference number is" in r.text:
			#reference = r.text.split("reference number is ")[1].split("<")[0]
			#assigned_id = self.view_reservations(date)[reference]['assigned_id']
			#return True, reference, assigned_id
			return True
		#else: return False, None, None
		else: return False
	
	def reserve(self, date, hour_start, hour_end, roomId):
		print(f"RESERVE: date={date}, segment=({hour_start},{hour_end}), resource={roomId}")
		#if not self._LOGIN: return False, None, None
		if not self._LOGIN: return False
		else: return self._reservation_post(date, hour_start, hour_end, roomId, "save")

	def update(self, reference, assigned_id, roomId, date, hour_start, hour_end):
		print(f"UPDATE: date={date}, segment=({hour_start},{hour_end}), resource={roomId}, reference={reference}, assigned_id={assigned_id}")
		#if not self._LOGIN: return False, None, None
		if not self._LOGIN: return False
		else: return  self._reservation_post(date, hour_start, hour_end, roomId, "update", assigned_id, reference)
