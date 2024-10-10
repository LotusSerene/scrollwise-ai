// frontend/src/utils/auth.js
import jwtDecode from 'jwt-decode';

export const getAuthToken = () => {
  return localStorage.getItem('token');
};

export const getUserId = () => {
  const token = getAuthToken();
  if (token) {
    const decodedToken = jwtDecode(token);
    return decodedToken.user_id || null;
  }
  return null;
};

export const setAuthToken = (token) => {
  localStorage.setItem('token', token);
};

export const removeAuthToken = () => {
  localStorage.removeItem('token');
};
