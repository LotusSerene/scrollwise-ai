// frontend/src/components/Validity.js
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './Validity.css';
import { getAuthToken, getUserId } from '../utils/auth';

function Validity() {
  const [validityChecks, setValidityChecks] = useState([]);
  const [selectedCheck, setSelectedCheck] = useState(null);
  const userId = getUserId();

  useEffect(() => {
    fetchValidityChecks();
  }, [userId]);

  const fetchValidityChecks = async () => {
    try {
      const token = getAuthToken();
      const response = await axios.get(`${process.env.REACT_APP_API_URL}/api/validity-checks`, {
        headers: {
          'Authorization': `Bearer ${token}`
        },
        params: {
          user_id: userId
        }
      });
      setValidityChecks(response.data.validityChecks);
    } catch (error) {
      console.error('Error fetching validity checks:', error);
      if (error.response) {
        setValidityChecks([{ error: error.response.data.error }]);
      } else {
        setValidityChecks([{ error: 'An unexpected error occurred' }]);
      }
    }
  };

  const handleCheckClick = (check) => {
    setSelectedCheck(check);
  };

  const handleDeleteCheck = async (checkId) => {
    try {
      const token = getAuthToken();
      await axios.delete(`${process.env.REACT_APP_API_URL}/api/validity-checks/${checkId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        },
        params: {
          user_id: userId
        }
      });
      fetchValidityChecks(); // Refresh the list after deletion
      if (selectedCheck && selectedCheck.id === checkId) {
        setSelectedCheck(null);
      }
    } catch (error) {
      console.error('Error deleting validity check:', error);
    }
  };

  const formatCheck = (check) => {
    return {
      ...check,
      review: check.review || 'N/A',
      style_guide_adherence: check.style_guide_adherence ? 'Yes' : 'No',
      style_guide_feedback: check.style_guide_feedback || 'N/A',
      continuity: check.continuity ? 'Yes' : 'No',
      continuity_feedback: check.continuity_feedback || 'N/A',
      test_results: check.test_results || 'N/A'
    };
  };

  return (
    <div className="validity-container">
      <div className="validity-sidebar">
        <h2>Validity Checks</h2>
        <ul>
          {validityChecks.map((check) => (
            <li
              key={check.id}
              className={`validity-check ${selectedCheck && selectedCheck.id === check.id ? 'selected' : ''}`}
              onClick={() => handleCheckClick(check)}
            >
              {check.chapterTitle} : {check.isValid ? 'Valid' : 'Invalid'}
              <span className="remove-icon" onClick={() => handleDeleteCheck(check.id)}>❌</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="validity-content">
        {selectedCheck && (
          <div className="validity-details">
            <h3>{selectedCheck.chapterTitle}</h3>
            <p>Validity: {selectedCheck.isValid ? 'Valid' : 'Invalid'}</p>
            <div className="validity-details-section">
              <p><strong>Chapter ID:</strong> {selectedCheck.chapterId}</p>
              <p><strong>Chapter Title:</strong> {selectedCheck.chapterTitle}</p>
              <p><strong>Validity:</strong> {selectedCheck.isValid ? 'Valid' : 'Invalid'}</p>
              <p><strong>Feedback:</strong> {selectedCheck.feedback}</p>
              <p><strong>Review:</strong> {formatCheck(selectedCheck).review}</p>
              <p><strong>Style Guide Adherence:</strong> {formatCheck(selectedCheck).style_guide_adherence}</p>
              <p><strong>Style Guide Feedback:</strong> {formatCheck(selectedCheck).style_guide_feedback}</p>
              <p><strong>Continuity:</strong> {formatCheck(selectedCheck).continuity}</p>
              <p><strong>Continuity Feedback:</strong> {formatCheck(selectedCheck).continuity_feedback}</p>
              <p><strong>Test Results:</strong> {formatCheck(selectedCheck).test_results}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Validity;
