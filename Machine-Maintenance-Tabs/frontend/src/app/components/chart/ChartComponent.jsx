import React, { useState } from 'react';
import axios from 'axios';
import { Bar, Pie } from 'react-chartjs-2';
import 'chart.js/auto';

const ChartComponent = () => {
  const [chartData, setChartData] = useState(null);
  const [error, setError] = useState(null);
  const [isBarChart, setIsBarChart] = useState(true);
  const [groupedData, setGroupedData] = useState({});

  const fetchChartData = async () => {
    try {
      const response = await axios.get('http://localhost:5000/get_excel_data');
      const data = response.data;
      console.log('data from backend', data);

      if (data.length <= 1) {
        setError('No data available');
        return;
      }

      const labels = [];
      const values = [];
      const grouped = {};

      data.slice(1).forEach((row, index) => {
        console.log(`Row ${index + 2}:`, row);
        if (row.SalesMan && row.Item && row.Sale_amt) {
          const label = `${row.SalesMan} - ${row.Item}`;
          labels.push(label);
          values.push(row.Sale_amt);

          if (!grouped[row.SalesMan]) {
            grouped[row.SalesMan] = [];
          }
          grouped[row.SalesMan].push({ item: row.Item, amount: row.Sale_amt });
        } else {
          console.warn(`Row ${index + 2} does not have enough columns`);
        }
      });

      console.log('Labels:', labels);
      console.log('Values:', values);
      console.log('Grouped Data:', grouped);

      const commonDataset = {
        label: 'Sales Data',
        data: values,
        backgroundColor: [
          'rgba(75, 192, 192, 0.2)',
          'rgba(54, 162, 235, 0.2)',
          'rgba(255, 206, 86, 0.2)',
          'rgba(75, 192, 192, 0.2)',
          'rgba(153, 102, 255, 0.2)',
          'rgba(255, 159, 64, 0.2)',
        ],
        borderColor: [
          'rgba(75, 192, 192, 1)',
          'rgba(54, 162, 235, 1)',
          'rgba(255, 206, 86, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(153, 102, 255, 1)',
          'rgba(255, 159, 64, 1)',
        ],
        borderWidth: 1,
      };

      setChartData({
        labels,
        datasets: [commonDataset],
      });

      setGroupedData(grouped);
      setError(null);
    } catch (error) {
      console.error('Error fetching chart data:', error);
      setError('Error fetching chart data from server');
    }
  };

  const toggleChart = () => {
    setIsBarChart(!isBarChart);
  };

  return (
    <div>
      <div className="App-header">
        <h1>Excel Data Visualization</h1>
      </div>
      <div className="content">
        <button onClick={fetchChartData}>
          Fetch Excel Data
        </button>
        <button onClick={toggleChart} style={{ marginLeft: '10px' }}>
          Switch to {isBarChart ? 'Pie Chart' : 'Bar Chart'}
        </button>
        <div className="chart-container" style={{ textAlign: 'center' }}>
          {error ? (
            <div>Error: {error}</div>
          ) : chartData ? (
            isBarChart ? (
              <Bar data={chartData} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', maxWidth: '90%', overflow: 'auto', marginTop: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', marginBottom: '20px' }}>
                  {Object.keys(groupedData).map((salesman, index) => (
                    <div key={index} style={{ margin: '0 20px' }}>
                      <h4>{salesman}</h4>
                      {groupedData[salesman].map((itemData, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', marginBottom: '5px' }}>
                          <div
                            style={{
                              display: 'inline-block',
                              width: '12px',
                              height: '12px',
                              backgroundColor: chartData.datasets[0].backgroundColor[chartData.labels.indexOf(`${salesman} - ${itemData.item}`)],
                              marginRight: '5px',
                            }}
                          ></div>
                          {itemData.item} - ${itemData.amount}
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
                <div style={{ width: '80%', maxWidth: '600px', height: '400px' }}>
                  <Pie
                    data={chartData}
                    options={{
                      plugins: {
                        legend: {
                          display: false,
                        },
                      },
                      maintainAspectRatio: false,
                    }}
                  />
                </div>
              </div>
            )
          ) : (
            <div>Loading...</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChartComponent;
