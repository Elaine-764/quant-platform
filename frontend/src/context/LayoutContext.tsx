import React, { createContext, useState, useContext, ReactNode, useEffect } from 'react'

export type Layout = 'horizontal' | 'vertical'

interface LayoutContextType {
    layout: Layout
    toggleLayout: () => void
}

const LayoutContext = createContext<LayoutContextType | undefined>(undefined)

export function LayoutProvider({ children }: { children: ReactNode }) {
    const [layout, setLayout] = useState<Layout>(() => {
        const stored = localStorage.getItem('layout')
        return (stored as Layout) || 'horizontal'
    })

    useEffect(() => {
        localStorage.setItem('layout', layout)
    }, [layout])

    const toggleLayout = () => {
        setLayout((prev) => (prev === 'horizontal' ? 'vertical' : 'horizontal'))
    }

    return (
        <LayoutContext.Provider value={{ layout, toggleLayout }}>
            {children}
        </LayoutContext.Provider>
    )
}

export function useLayout() {
    const context = useContext(LayoutContext)
    if (!context) {
        throw new Error('useLayout must be used within LayoutProvider')
    }
    return context
}
