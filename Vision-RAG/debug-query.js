#!/usr/bin/env node

// Debug script to inspect query results and image URLs
const API_BASE = 'http://127.0.0.1:8000';

async function debugQuery() {
  console.log('🔍 Debugging Vision-RAG Query Results...\n');

  try {
    console.log('Testing query endpoint with detailed response...');
    const formData = new FormData();
    formData.append('question', 'show me some objects');
    formData.append('k', '3');

    const queryResponse = await fetch(`${API_BASE}/query-image`, {
      method: 'POST',
      body: formData,
    });
    
    if (queryResponse.ok) {
      const queryData = await queryResponse.json();
      console.log('✅ Query successful');
      console.log('Method:', queryData.method);
      console.log('Results count:', queryData.results?.length || 0);
      
      if (queryData.results && queryData.results.length > 0) {
        console.log('\n📋 First result details:');
        const firstResult = queryData.results[0];
        console.log('- ID:', firstResult.id);
        console.log('- Content:', firstResult.content);
        console.log('- Score:', firstResult.score);
        console.log('- URI:', firstResult.uri);
        console.log('- Meta:', firstResult.meta);
        console.log('- Display Info:', JSON.stringify(firstResult.display_info, null, 2));
        
        // Test image serving endpoint if we have a URI
        if (firstResult.display_info?.image_url) {
          console.log('\n🖼️ Testing image URL:', firstResult.display_info.image_url);
          try {
            const imageResponse = await fetch(firstResult.display_info.image_url);
            console.log('Image response status:', imageResponse.status);
            console.log('Image response headers:', Object.fromEntries(imageResponse.headers.entries()));
          } catch (error) {
            console.log('❌ Image fetch failed:', error.message);
          }
        }
      }
    } else {
      console.log('❌ Query failed:', queryResponse.status, queryResponse.statusText);
      const errorText = await queryResponse.text();
      console.log('Error details:', errorText);
    }
  } catch (error) {
    console.log('❌ Query test failed:', error.message);
  }
}

// Run the debug
debugQuery().catch(console.error);