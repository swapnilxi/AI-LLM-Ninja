import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'
import WebSearch from './components/WebSearch'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <WebSearch />
    </>
  )
}

export default App
