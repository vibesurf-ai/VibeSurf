import pdb

import httpx

def singleton(cls):
	instance = [None]

	def wrapper(*args, **kwargs):
		if instance[0] is None:
			instance[0] = cls(*args, **kwargs)
		return instance[0]

	return wrapper

def get_vibesurf_version() -> str:
	import vibe_surf
	return str(vibe_surf.__version__)

async def check_latest_vibesurf_version() -> str | None:
	"""Check the latest version of browser-use from PyPI asynchronously.

	Returns:
		The latest version string if successful, None if failed
	"""
	try:
		async with httpx.AsyncClient(timeout=3.0) as client:
			response = await client.get('https://pypi.org/pypi/vibesurf/json')
			if response.status_code == 200:
				data = response.json()
				return data['info']['version']
	except Exception:
		# Silently fail - we don't want to break agent startup due to network issues
		pass
	return None