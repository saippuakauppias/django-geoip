# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from .utils import get_class


class BaseLocationStorage(object):
    """ Base class for user location storage
    """
    def __init__(self, request, response):
        self.request = request
        self.response = response
        self.location_model = get_class(settings.GEOIP_LOCATION_MODEL)

    def get(self):
        raise NotImplemented

    def set(self, location=None, force=False):
        raise NotImplemented

    def _validate_location(self, location):
        if location == settings.GEOIP_LOCATION_EMPTY_VALUE:
            return True
        if not isinstance(location, self.location_model):
            return False
        try:
            return self.location_model.objects.filter(pk=location.id).exists()
        except AttributeError:
            raise

    def _get_by_id(self, location_id):
        return self.location_model.get_available_locations().get(pk=location_id)


class LocationDummyStorage(BaseLocationStorage):
    """ Fake storage for debug or when location doesn't neet to be stored
    """
    def get(self):
        return getattr(self.request, 'location', None)

    def set(self, location=None, force=False):
        pass


class LocationCookieStorage(BaseLocationStorage):
    """ Class that deals with saving user location on client's side (cookies)
    """

    def __init__(self, *args, **kwargs):
        super(LocationCookieStorage, self).__init__(*args, **kwargs)
        self.cookie_name = settings.GEOIP_COOKIE_NAME
        self.location_attr = 'location'

    def _get_location_id(self):
        return self.request.COOKIES.get(self.cookie_name, None)

    def get(self):
        location_id = self._get_location_id()

        if location_id:
            try:
                return self._get_by_id(location_id)
            except (ObjectDoesNotExist, ValueError):
                pass
        return None

    def set(self, location=None, force=False):
        if not self._validate_location(location):
            raise ValueError
        empty_value = settings.GEOIP_LOCATION_EMPTY_VALUE
        cookie_value = empty_value if location == empty_value else location.id
        if force or self._should_update_cookie(cookie_value):
            self._do_set(cookie_value)

    def get_cookie_domain(self):
        if settings.GEOIP_COOKIE_DOMAIN:
            return settings.GEOIP_COOKIE_DOMAIN
        else:
            return None

    def _do_set(self, value):
        self.response.set_cookie(
            key=self.cookie_name,
            value=value,
            domain=self.get_cookie_domain(),
            expires=datetime.utcnow() + timedelta(seconds=settings.GEOIP_COOKIE_EXPIRES))

    def _should_update_cookie(self, new_value):
        # process_request never completed, don't need to update cookie
        if not hasattr(self.request, self.location_attr):
            return False
        # Cookie doesn't exist, we need to store it
        if self.cookie_name not in self.request.COOKIES:
            return True
        # Cookie is obsolete, because we've changed it's value during request
        if str(self._get_location_id()) != str(new_value):
            return True
        return False


class CurrentLocationCookieStorage(LocationCookieStorage):

    def __init__(self, *args, **kwargs):
        super(LocationCookieStorage, self).__init__(*args, **kwargs)
        self.cookie_name = settings.GEOIP_CURRENT_LOCATION_COOKIE_NAME
        self.location_attr = 'current_location'

    def get(self):
        result = super(CurrentLocationCookieStorage, self).get()
        if result is None:
            return settings.GEOIP_LOCATION_EMPTY_VALUE
