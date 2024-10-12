// frontend/src/utils/auth.js
import { jwtDecode } from 'jwt-decode';

export const getAuthToken = () => {
  return localStorage.getItem('token');
};

export const getUserId = () => {
  const token = getAuthToken();
  if (token) {
    const decodedToken = jwtDecode(token);
    return decodedToken.sub || null;
  }
  return null;
};

export const setAuthToken = (token) => {
  localStorage.setItem('token', token);
};

export const removeAuthToken = () => {
  localStorage.removeItem('token');
};

export const getAuthHeaders = () => {
  const token = getAuthToken();
  if (token) {
    // Check if the token has the correct format
    if (token.split('.').length !== 3) {
      console.error('Invalid token format');
      return {};
    }
    return {
      'Authorization': `Bearer ${token}`
    };
  }
  console.warn('No auth token found');
  return {};
};
