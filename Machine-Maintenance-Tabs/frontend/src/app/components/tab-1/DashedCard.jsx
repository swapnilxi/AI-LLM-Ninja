import React from 'react'

function DashedCard({heading, data}) {
  return (
    <div>
        <div class="border-dashed border-2 border-[#679436]
         p-8 flex flex-col w-[295px] h-[130px] justify-center items-center rounded-md ">
            <div className="font-semibold text-center">
             {heading}
            </div>
            <div className="p-2"></div>
            <div className="font-semibold text-center">
             {data}
            </div>
         </div>


    </div>
  )
}

export default DashedCard