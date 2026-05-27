from rest_framework.throttling import UserRateThrottle


class CommentCreateThrottle(UserRateThrottle):
    rate = '10/min'
