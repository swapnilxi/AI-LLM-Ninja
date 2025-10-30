#!/usr/bin/env node

// Simple test script to verify frontend-backend connection
const API_BASE = 'http://127.0.0.1:8000';

async function testConnection() {
  console.log('🔍 Testing Vision-RAG Frontend-Backend Connection...\n');

  // Test 1: Health Check
  try {
    console.log('1. Testing health endpoint...');
    const healthResponse = await fetch(`${API_BASE}/`);
    const healthData = await healthResponse.json();
    console.log('✅ Health check passed:', healthData);
  } catch (error) {
    console.log('❌ Health check failed:', error.message);
    return;
  }

  // Test 2: Query endpoint (text only)
  try {
    console.log('\n2. Testing query endpoint with text...');
    const formData = new FormData();
    formData.append('question', 'test query');
    formData.append('k', '3');

    const queryResponse = await fetch(`${API_BASE}/query-image`, {
      method: 'POST',
      body: formData,
    });
    
    if (queryResponse.ok) {
      const queryData = await queryResponse.json();
      console.log('✅ Query endpoint accessible');
      console.log('Response method:', queryData.method);
      console.log('Results count:', queryData.results?.length || 0);
    } else {
      console.log('⚠️ Query endpoint returned:', queryResponse.status, queryResponse.statusText);
    }
  } catch (error) {
    console.log('❌ Query test failed:', error.message);
  }

  // Test 3: CORS headers
  try {
    console.log('\n3. Testing CORS configuration...');
    const corsResponse = await fetch(`${API_BASE}/`, {
      method: 'OPTIONS',
      headers: {
        'Origin': 'http://localhost:3000',
        'Access-Control-Request-Method': 'POST',
      }
    });
    console.log('✅ CORS test completed');
  } catch (error) {
    console.log('❌ CORS test failed:', error.message);
  }

  console.log('\n🎉 Connection test completed!');
}

// Run the test
testConnection().catch(console.error);