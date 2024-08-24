
import React, { useEffect } from 'react';
import DashedCard from './DashedCard'
import UploadComponent from './UploadComponent'
import TurboFanTable from './TableComp'
import useTurbofanStore from './useTurboFanStore'
import TableComponent from './TableComponent'

function TurbofanPage() {
  const { fetchData, TurboFanData } = useTurbofanStore();

  useEffect(() => {
    fetchData(null);
  }, [fetchData]);

  const handleFileUpload = (file) => {
    fetchData(file);
  };

  return (
    <div>
      <div>
        <UploadComponent onFileUpload={handleFileUpload} />
      </div>

      <div className="bg-gradient-to-r from-white to-[#679436] ...">
        <div className="flex justify-center items-center w-full h-[51px] font-semibold text-center"> Key Summary </div>
      </div>
      
      <div className="py-6">
        <div className="font-semibold text-[36px] leading-normal">RUL Prediction</div>
        <div className="w-[309px] h-[5px] bg-black"></div>
      </div>
      
      <div>
        <div className='flex items-center justify-between gap-3 p-4'>
          <DashedCard heading={"Avg remaining useful life"} data={`${TurboFanData.avg_rul}%`} />
          <DashedCard heading={"Total Assets"} data={`${TurboFanData.total_assets}`} />
          <DashedCard heading={"In Use Assets"} data={`${TurboFanData.in_use}`} />
          <DashedCard heading={"Retired Assets"} data={`${TurboFanData.retired}`} />
        </div>
      </div>
      
      <TurboFanTable data={TurboFanData} />
    </div>
  );
}

export default TurbofanPage;

