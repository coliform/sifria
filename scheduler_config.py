DEBUG = False

URL_BASE     = "FILL_URL_BASE"

USERNAME     = "FILL_USERNAME"
PASSWORD     = "FILL_PASSWORD"

DAYS = {
	'Sunday':    [(10, 16)],
	'Monday':    [(12,17)],#[(10, 16)],
	'Tuesday':   [(10, 16)],
	'Wednesday': [(8, 14)],
	'Thursday':  [],#[(12,18)],
    'Friday':    [],
    'Saturday':  []
}
# Room 13, 14, 15
OPTIONS = {
	'23','24','25'
}

if "FILL_" in URL_BASE or "FILL_" in USERNAME or "FILL_" in PASSWORD:
	print("Fix scheduler_config.py and try again!")
	exit()
