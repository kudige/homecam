import React from 'react'

export default function DatePicker({ value, onChange }){
  return (
    <input type="date" value={value} onChange={e=>onChange(e.target.value)} />
  )
}
