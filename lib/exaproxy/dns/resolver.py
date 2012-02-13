#!/usr/bin/env python
# encoding: utf-8
"""
resolver.py

Created by David Farrar on 2012-02-08.
Copyright (c) 2011 Exa Networks. All rights reserved.
"""

import random

from factory.request import DNSRequestFactory
from factory.response import DNSResponseFactory
from network.udp import UDPFactory
from network.tcp import TCPFactory

class ConfigurationError(Exception):
	pass

class DNSResolver:
	udp_socket_factory = UDPFactory()
	tcp_socket_factory = TCPFactory()
	request_factory = DNSRequestFactory()
	response_factory = DNSResponseFactory()

	UDP_MAXLEN=512

	def __init__(self, resolv='/etc/resolv.conf'):
		config = self._parse(resolv)

		if not config:
			raise ConfigurationError, 'Could not read resolver configuration from %s' % resolv

		self.servers = config['nameserver']
		self._nextid = 0

	@property
	def nextid(self):
		res = self._nextid
		self._nextid += 1
		return res

	@property
	def server(self):
		return random.choice(self.servers)

	def _parse(self, filename):
		try:
			result = {'nameserver': []}

			with open(filename) as fd:
				for line in (line.strip() for line in fd):
					if line.startswith('#'):
						continue

					option, value = (line.split(None, 1) + [''])[:2]
					if option == 'nameserver':
						result['nameserver'].extend(value.split())
		except (TypeError, IOError):
			result = None

		return result


	def lookup(self, hostname, rdtype):
		request_s = self.request_factory.createRequestString(self.nextid, rdtype, hostname)

		if len(request_s) < self.UDP_MAXLEN:
			socket = self.udp_socket_factory.create(self.server, 53)
			socket.send(request_s)

			response_s = socket.recv(1024)
			response = self.response_factory.normalizeResponse(response_s)

			info = response.getResponse()

		return info


	def extract(self, hostname, rdtype, info, seen=[]):
		data = info.get(hostname)

		# query again in case we should have this info
		# is this needed?
		if seen and not data:
			info = self.lookup(hostname, rdtype)
			data = info.get(hostname)

		if data:
			if rdtype in data:
				resolved = random.choice(data[rdtype])

			elif rdtype != 'CNAME':
				cnames = [cname for cname in data.get('CNAME', []) if cname not in seen]
				seen = seen + cnames # do not modify seen

				for cname in cnames:
					res = self.extract(cname, rdtype, info, seen)
					if res:
						resolved = res
						break
				else:
					resolved = None
			else:
				resolved = None
		else:
			resolved = None

		return resolved



	def resolve(self, hostname, rdtype='A'):
		info = self.lookup(hostname, rdtype)
		resolved = self.extract(hostname, rdtype, info)
		if not resolved and rdtype == 'A':
			info = self.lookup(hostname, 'AAAA')
			resolved = self.extract(hostname, 'AAAA', info)

		return resolved


if __name__ == '__main__':
	import sys
	resolver = DNSResolver()

	if len(sys.argv) >= 2:
		url = sys.argv[1]
	else:
		url = 'www.exa-networks.co.uk'

	print resolver.resolve(url)