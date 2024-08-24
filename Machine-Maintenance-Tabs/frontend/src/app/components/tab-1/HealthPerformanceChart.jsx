"use client";

import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  annotationPlugin
);

const HealthPerformanceChart = ({ data, highlightedValue }) => {
  const labels = Array.from({ length: 61 }, (_, i) => 60 - i); 
  const visibleData = [98, 95, 90, 75, 50, 30, 0];
  highlightedValue = parseInt(highlightedValue, 10)
  console.log ('chartdata' , data)
  console.log ('highlightedvalue' , highlightedValue)
  
 
  const dataExtended = new Array(61).fill(null).map((_, index) => {
    const x = 60 - index;
    const step = 10; 

   
    if (x % step === 0) {
      return visibleData[visibleData.length - 1 - x / step];
    } else {
      const prevIndex = Math.floor(x / step) * step;
      const nextIndex = prevIndex + step;
      const t = (x - prevIndex) / step;
      const prevValue = visibleData[visibleData.length - 1 - prevIndex / step];
      const nextValue = visibleData[visibleData.length - 1 - nextIndex / step];
      return prevValue + (nextValue - prevValue) * t;
    }
  });


  const highlightedIndex = highlightedValue !== null ? 60 - highlightedValue : null;
  console.log("Highlighted Index (as integer):", highlightedIndex);

  const highlightedY = highlightedIndex !== null ? dataExtended[highlightedIndex] : null;
  console.log ('highlightedindex' , highlightedIndex)

  const getYValueForX = (xValue) => {
    const index = 60 - xValue;
    return dataExtended[index];
  };

  const chartData = {
    labels: labels,
    datasets: [
      {
        label: 'Component Health/Performance',
        data: dataExtended,
        borderColor: (context) => {
          const index = context.dataIndex;
          const x = 60 - index;
          if (x > 18 && x <= 36) {
            return 'orange';
          }
          if (x <= 18) {
            return 'red';
          }
          return 'green';
        },
        borderWidth: 1,
        pointRadius: 0,
        fill: false,
        tension: 0.4, 
        segment: {
          borderColor: (context) => {
            const index = context.p0DataIndex;
            const x = 60 - index;
            if (x > 18 && x <= 36) {
              return 'orange';
            }
            if (x <= 20) {
              return 'red'; 
            }
            return 'green';
          },
        },
      },
    ],
  };

  const options = {
    scales: {
      x: {
        title: {
          display: true,
          text: 'Cycles',
        },
        ticks: {
          autoSkip: false,
          maxRotation: 0,
          minRotation: 0,
          callback: function (value, index) {
            if ([0, 10, 20, 30, 40, 50, 60].includes(index)) {
              return 60 - index;
            }
            return '';
          },
          color: (context) => (context.tick === highlightedValue ? 'black' : 'black'),
        },
        grid: {
          display: false,
        },
      },
      y: {
        title: {
          display: true,
          text: 'Component Health/Performance',
        },
        ticks: {
          display: false,
        },
        grid: {
          display: false,
        },
        min: 0,
        max: 100, 
      },
    },
    plugins: {
      legend: {
        display: false,
      },
      annotation: {
        annotations: {
          repair: {
            type: 'line',
            mode: 'vertical',
            scaleID: 'x',
            value: 42, 
            borderColor: 'red',
            borderWidth: 1,
            borderDash: [5, 5],
            yMin: 0, 
            yMax: getYValueForX(20), 
            label: {
              enabled: true,
              content: 'Repair',
              position: 'top',
              backgroundColor: 'red',
            },
          },
          caution: {
            type: 'line',
            mode: 'vertical',
            scaleID: 'x',
            value: 24, 
            borderColor: 'orange',
            borderWidth: 1,
            borderDash: [5, 5],
            yMin: 0, 
            yMax: getYValueForX(38), 
            label: {
              enabled: true,
              content: 'Caution',
              position: 'top',
              backgroundColor: 'orange',
            },
          },
          highlightedValue: highlightedIndex !== null && highlightedY !== null ? {
            type: 'line',
            mode: 'vertical',
            scaleID: 'x',
            value: highlightedIndex,
            borderColor: 'black',
            borderWidth: 1,
            borderDash: [5, 5],
            yMin: 0,
            yMax: highlightedY,
            label: {
              enabled: true,
              content: `Value: ${highlightedValue}`,
              position: 'top',
              backgroundColor: 'black',
            },
          } : null,
        },
      },
    },
    maintainAspectRatio: false,
    responsive: true,
  };

  return (
    <div style={{ backgroundColor: 'white', padding: '20px', width: '100%', height: '100%' }}>
      <Line data={chartData} options={options} />
    </div>
  );
};

export default HealthPerformanceChart;
