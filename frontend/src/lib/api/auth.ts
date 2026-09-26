import type { MessageResponse, ResetToken, User } from "@/types/api";
import { http } from "./client";

export interface SignupPayload {
  login_id: string;
  email: string;
  full_name: string | null;
  password: string;
  confirm_password: string;
}

export interface LoginPayload {
  login_id: string;
  password: string;
}

export interface ResetPasswordPayload {
  reset_token: string;
  password: string;
  confirm_password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  password: string;
  confirm_password: string;
}

export interface UpdateProfilePayload {
  full_name?: string | null;
  email?: string;
}

/** Sessions, the password-reset flow and the signed-in user's own profile. */
export const authApi = {
  signup: (payload: SignupPayload) => http.post<User>("/auth/signup", payload),
  login: (payload: LoginPayload) => http.post<User>("/auth/login", payload),
  logout: () => http.post<MessageResponse>("/auth/logout"),
  logoutEverywhere: () => http.post<MessageResponse>("/auth/logout-all"),
  me: () => http.get<User>("/auth/me"),

  forgotPassword: (email: string) =>
    http.post<MessageResponse>("/auth/forgot-password", { email }),
  verifyOtp: (email: string, otp: string) =>
    http.post<ResetToken>("/auth/verify-otp", { email, otp }),
  resetPassword: (payload: ResetPasswordPayload) =>
    http.post<MessageResponse>("/auth/reset-password", payload),

  profile: () => http.get<User>("/users/me"),
  updateProfile: (payload: UpdateProfilePayload) => http.patch<User>("/users/me", payload),
  changePassword: (payload: ChangePasswordPayload) =>
    http.post<MessageResponse>("/users/me/password", payload),
};
