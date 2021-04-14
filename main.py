#!/usr/bin/env python3

from scheduler_config import *

import requests
import pickle
import base64
import random
import string
import json
import time
from requests_toolbelt import MultipartEncoder
import datetime as DT
from scheduler import Session

def pad_num(num):
	return ("" if num>=10 else "0") + str(num)

now = DT.datetime.now()
next_week = now + DT.timedelta(days=7)

today = pad_num(now.year)+"-"+pad_num(now.month)+"-"+pad_num(now.day)
next_week =  pad_num(next_week.year)+"-"+pad_num(next_week.month)+"-"+pad_num(next_week.day)
weekday = DT.datetime.today().strftime('%A')

def buncher(l):
	if type(l)!=list or len(l)==0: return []
	bunched = [(l[0], (0,1))]
	for t in range(len(l)):
		last = bunched.pop()
		if last[t]==last[0]: bunched.append((last[0],(last[1][0],last[1][1]+1)))
		else: bunched.append((last[0],(t,t+1)))
	return bunched


def save_session(session, excess):
	with open('session.object','wb') as f:
		f.write(pickle.dumps({'session': session, 'excess': excess}))

def load_session():
	try:
		with open('session.object','rb') as f:
			d = pickle.loads(f.read())
			session = d['session']
			excess = d['excess']
			return session, excess
	except:
		return None, None

'''class Resource:
	def __init__(self, name):
		self._occupied = []
		self.name = name

	def occupy(self, segment):
		self._occupied.append(segment)
		self._occupied.sort(key=lambda x: x[0])

	def is_occupied(self, segment):
		(tstart, tend) = (segment[0], segment[1])
		if tend-tstart <= 0: return False
		for occ_segment in self._occupied:
			if (occ_segment[0] < tstart and tstart < occ_segment[1]) or (occ_segment[1] < tend and tend < occ_segment[1]): return True
		return False

	def is_free(self, segment):
		return not self.is_occupied(segment)'''

class MarkedTimeline:
	def __init__(self, segment):
		self._start = segment[0]
		self._end   = segment[1]
		self.segments = []

	def __contains__(self, t):
		print(f"Hola checking {t}")
		if type(t)==tuple:
			if t[1] <= t[0]: raise Exception("t[0] should be smaller than t[1]")
			for segment in self.segments:
				if (segment[0] < t[1] and t[1] <= segment[1]) or (segment[0] <= t[0] and t[0] < segment[1]) \
					or (t[0] <= segment[0] and t[1] >= segment[1]): return True
			return False
		elif type(t)==int:
			for segment in self.segments:
				if segment[0] <= t and t < segment[1]: return True
			return False
		else: return False

	def __add__(self, segment): # keeps it sorted
		(s_start, s_end) = (segment[0], segment[1])
		if s_start < self._start or s_start >= self._end \
		   or s_end < self._start or s_end > self._end \
		   or s_end-s_start < 0: raise Exception("t[0] should be smaller than t[1]")
		if s_start == s_end: return self
		if len(self.segments) == 0:
			self.segments.append(segment)
			return self
		i = 0
		while i < len(self.segments):
			if self.segments[i][0] >= s_end: break
			i+=1
		if i >= len(self.segments):
			self.segments = self.segments + [segment]
			return self
		print(f"append: self.segments={self.segments}, segment={segment}, i={i}")
		if self.segments[i][0] == s_end:
			print("hola")
			print(self.segments[:max(0,i-1)])
			print( [(segment[0],self.segments[i][1])])
			print(self.segments[i+1:])
			self.segments = self.segments[:max(0,i-1)] + [(segment[0],self.segments[i][1])] + self.segments[i+1:]
		else: self.segments = self.segments[:max(0,i-1)] + [segment] + self.segments[i:]
		return self

	def __and__(self, segment):
		(s_start, s_end) = (segment[0], segment[1])
		intersection = []
		last_start, last_end = s_start, s_start+1
		intersecting = False
		while last_end <= s_end:
			if (last_start,last_end) in self: intersecting = True
			else:
				if intersecting: intersection.append((last_start,last_end))
				intersecting = False
				last_start = last_end
			last_end += 1
		if intersecting: intersection.append((last_start,last_end))
		return intersection

	def inverse(self):
		timeline = MarkedTimeline((self._start, self._end))
		last_start = self._start
		last_end = last_start+1
		while last_end <= self._end:
			if (last_start, last_end) in self:
				if last_end-last_start >= 2:
					timeline += (last_start, last_end-1)
				last_start = last_end
			last_end += 1
		last_end -= 1
		if last_end-last_start >= 1 and (last_start,last_end) not in self:
			timeline += (last_start,last_end)
		print(timeline.segments)
		return timeline

	def __str__(self):
		return str(self.segments)


class Resource:
	def __init__(self, name):
		self._occupied = MarkedTimeline((0,24))
		self.name = name

	def occupy(self, segment):
		self._occupied += segment

	def is_occupied(self, segment):
		return segment in self._occupied

	def is_free(self, segment):
		return not self.is_occupied(segment)

	def free_until(self, hour, until):
		for i in range(hour,until):
			if i in self._occupied: return i
		return until


class Day:
	def __init__(self, resource_names=OPTIONS, occupants=None):
		self._resources = {}
		self._bookings = {}
		for name in resource_names:
			self._resources[name] = Resource(name)
		for occupant in occupants:
			occupant=occupants[occupant]
			resource = occupant['resource']
			segment = (occupant['hour_start'],occupant['hour_end'])
			self.occupy(resource, segment)

	def occupy(self, resource, segment):
		if resource not in self._resources: return
		self._resources[resource].occupy(segment)

	def is_free(self, resource, segment):
		if resource not in self._resources: return False
		return self._resources[resource].is_free(segment)

	def suggest_booking(self, segment):
		(tstart, tend) = (segment[0], segment[1])
		if tstart >= tend: return []
		
		required_inorder = []

		current_start = tstart
		while current_start < tend:
			found = False
			for name in self._resources:
				free_until = self._resources[name].free_until(current_start, tend)
				print(f"{name} is free between {current_start}-{free_until}")
				print(f"{str(self._resources[name]._occupied)}")
				if free_until > current_start:
					self._resources[name].occupy((current_start, free_until))
					required_inorder.append((name, (current_start, free_until)))
					current_start = free_until
					found = True
					break
			if not found:
				current_start += 1
		return required_inorder
		#return ([None]*tstart) + required_inorder, tuples_inorder


known_schedules = {} # lists endings
# known_schedules[str_date][str_hour] = True/False/noexistant = did we schedule anything to end at str_hour?

def blast(date, segment):
	(tstart, tend) = (segment[0], segment[1])
	scheduler = Session(USERNAME, PASSWORD, LOGIN=not DEBUG)

	all_orders = {'6050b4e1b1a58742044261': {'owner': True, 'assigned_id': '33161', 'reference': '6050b4e1b1a58742044261', 'resource': '23', 'hour_start': 8, 'hour_end': 10}, '603522a255478737116334': {'owner': False, 'assigned_id': 
'31841', 'reference': '603522a255478737116334', 'resource': '29', 'hour_start': 10, 'hour_end': 12}, '60352df086909778952203': {'owner': False, 'assigned_id': '31892', 'reference': '60352df086909778952203', 'resource': '28', 'hour_start': 11, 'hour_end': 12}, '603e41ce30144970761761': {'owner': False, 'assigned_id': '32286', 'reference': '603e41ce30144970761761', 'resource': '26', 'hour_start': 12, 'hour_end': 15}, '603bbbbf24288855924547': {'owner': False, 'assigned_id': '32042', 'reference': '603bbbbf24288855924547', 'resource': '29', 'hour_start': 14, 'hour_end': 16}}
	if scheduler._LOGIN: all_orders=scheduler.view_reservations(date)
	all_orders = { key:value for (key,value) in all_orders.items() if value['hour_end'] > tstart and value['hour_start'] < tend}
	mine     = { key:value for (key,value) in all_orders.items() if value['owner']}
	occupied = { key:value for (key,value) in all_orders.items() if not value['owner']}
	#print(occupied)

	day = Day(occupants=occupied)

	my_starts = []
	my_ends = []
	for reference in mine:
		my_starts.append(mine[reference]['hour_start'])
		my_ends.append(mine[reference]['hour_end'])

	mine_new = {}
	for reference in mine:
		order = mine[reference]
		known_schedules[date][order['hour_end']] = True
		resource = order['resource']
		# expand right until we hit a barrier or segment end
		new_right = order['hour_end'] + 1
		while new_right <= tend and new_right-1 not in my_starts and day.is_free(resource, (order['hour_start'], new_right)): new_right += 1
		new_right -= 1 # last one is surely bad
		# same but left
		new_left = order['hour_start'] - 1
		while new_left >= tstart and new_left+1 not in my_ends and day.is_free(resource, (new_left, new_right)): new_left -= 1
		new_left += 1
		# can't morph like this but ok
		order['update'] = new_left!=mine[reference]['hour_start'] or new_right!=mine[reference]['hour_end']
		order['hour_start'] = new_left
		order['hour_end'] = new_right
		mine_new[reference] = order

	my_starts = []
	my_ends = []
	my_timeline = MarkedTimeline(segment)
	for reference in mine_new:
		order = mine_new[reference]
		print(order)
		my_timeline = my_timeline + (max(order['hour_start'],tstart),min(order['hour_end'],tend))
		if not order['update']: continue
		scheduler.update(reference, order['assigned_id'], order['resource'], date, order['hour_start'], order['hour_end'])
	my_missing = my_timeline.inverse()

	# now we only create wherever blank
	for subseg in my_missing.segments:
		tuples = day.suggest_booking(subseg)
		for book in tuples:
			resource = book[0]
			hour_start = book[1][0]
			hour_end = book[1][1]
			scheduler.reserve(date, hour_start, hour_end, resource)


'''now = DT.datetime.now()
date = now + DT.timedelta(days=7)
weekday = date.strftime('%A')
date = pad_num(date.year)+'-'+pad_num(date.month)+'-'+pad_num(date.day)
hour_start = DAYS[weekday][0][0]
hour_end = DAYS[weekday][0][1]
blast(date, (8,12))'''

def wait_for_next_hour():
	now = DT.datetime.now()
	next_hour = DT.datetime.now() + DT.timedelta(hours=1)
	next_hour = next_hour.replace(microsecond=0, second=30, minute=0)
	time.sleep((next_hour-now).total_seconds())


run_loop = not DEBUG
while run_loop:
	now = DT.datetime.now()
	next_week = now + DT.timedelta(days=7)

	today = pad_num(now.year)+"-"+pad_num(now.month)+"-"+pad_num(now.day)
	next_week =  pad_num(next_week.year)+"-"+pad_num(next_week.month)+"-"+pad_num(next_week.day)
	if next_week not in known_schedules: known_schedules[next_week]={}
	weekday = DT.datetime.today().strftime('%A')

	for hours in DAYS[weekday]: # we can have multiple segments per day
		hour_start = hours[0]
		hour_end = min(now.hour, hours[1])
		if now.hour < hour_start+1 or now.hour > hour_end+1 \
			or now.hour in known_schedules[next_week]: continue
		blast(next_week, (hour_start, now.hour))

	known_schedules[next_week][now.hour] = True
	wait_for_next_hour()
