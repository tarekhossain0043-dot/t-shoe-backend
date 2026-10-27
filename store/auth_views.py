import re

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


def member_data(user):
    return {
        "id": user.pk,
        "name": user.first_name or user.username,
        "phone": user.username,
        "email": user.email,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def token_data(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": member_data(user),
    }


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        name = str(request.data.get("name", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        phone = re.sub(r"[\s()-]", "", str(request.data.get("phone", "")))
        password = str(request.data.get("password", ""))

        if not name or len(name) > 150:
            return Response({"detail": "Enter your name (up to 150 characters)."}, status=status.HTTP_400_BAD_REQUEST)
        if not re.fullmatch(r"\+?\d{8,15}", phone):
            return Response({"detail": "Enter a valid phone number with 8 to 15 digits."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_email(email)
        except ValidationError:
            return Response({"detail": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)
        if len(password) < 8:
            return Response({"detail": "Password must be at least 8 characters long."}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username__iexact=phone).exists():
            return Response({"detail": "An account with this phone number already exists."}, status=status.HTTP_409_CONFLICT)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "An account with this email address already exists."}, status=status.HTTP_409_CONFLICT)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=phone,
                    email=email,
                    first_name=name,
                    password=password,
                )
        except IntegrityError:
            return Response({"detail": "An account with these details already exists."}, status=status.HTTP_409_CONFLICT)

        return Response(token_data(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        identifier = str(request.data.get("identifier", "")).strip()
        password = str(request.data.get("password", ""))
        if not identifier or not password:
            return Response({"detail": "Enter your phone number or email and password."}, status=status.HTTP_400_BAD_REQUEST)

        user_query = {"email__iexact": identifier} if "@" in identifier else {"username__iexact": re.sub(r"[\s()-]", "", identifier)}
        user = User.objects.filter(**user_query).first()
        authenticated = authenticate(request, username=user.username, password=password) if user else None
        if authenticated is None or not authenticated.is_active:
            return Response({"detail": "The phone/email or password is incorrect."}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(token_data(authenticated), status=status.HTTP_200_OK)


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return Response({"detail": "Your session has expired. Please sign in again."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        try:
            refresh = RefreshToken(str(request.data.get("refresh", "")))
            refresh.blacklist()
        except TokenError:
            return Response({"detail": "The refresh token is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class CurrentMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": member_data(request.user)}, status=status.HTTP_200_OK)
