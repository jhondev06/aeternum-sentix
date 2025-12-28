"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import api from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { LogOut, TrendingUp, TrendingDown, Minus } from "lucide-react"

interface SentimentData {
    ticker: string
    bucket_start: string
    mean_sent: number
    prob_up?: number // Not in realtime endpoint by default? Wait, realtime returns sentiment stats. /probabilities returns prob.
    count: number
}

interface ProbabilityData {
    ticker: string
    prob_up: number
    prob_down: number
    decision: string
}

export default function DashboardPage() {
    const [data, setData] = useState<SentimentData[]>([])
    const [scores, setScores] = useState<Record<string, ProbabilityData>>({})
    const [loading, setLoading] = useState(true)
    const router = useRouter()

    const fetchData = async () => {
        try {
            // 1. Get Realtime Sentiment
            const resRealtime = await api.get("/realtime")
            const items: SentimentData[] = resRealtime.data.data
            setData(items)

            // 2. Get Probabilities for each ticker (could be optimized)
            const newScores: Record<string, ProbabilityData> = {}
            for (const item of items) {
                try {
                    // Note: /signal endpoint gives decision
                    const resSignal = await api.get("/signal", { params: { ticker: item.ticker } })
                    newScores[item.ticker] = resSignal.data
                } catch (e) {
                    console.error(`Failed to get signal for ${item.ticker}`, e)
                }
            }
            setScores(newScores)

        } catch (err) {
            console.error(err)
            // Redirect to login if unauthorized
            router.push("/login")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        // Check auth
        const token = localStorage.getItem("token")
        if (!token) {
            router.push("/login")
            return
        }

        fetchData()
        const interval = setInterval(fetchData, 60000) // Refresh every minute
        return () => clearInterval(interval)
    }, [router])

    const handleLogout = () => {
        localStorage.removeItem("token")
        localStorage.removeItem("username")
        router.push("/login")
    }

    if (loading) {
        return <div className="flex h-screen items-center justify-center">Loading...</div>
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            <header className="bg-white dark:bg-gray-800 shadow">
                <div className="container mx-auto px-4 py-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold text-gray-900 dark:text-white">Aeternum Sentix Dashboard</h1>
                    <Button variant="outline" onClick={handleLogout} className="flex items-center gap-2">
                        <LogOut className="h-4 w-4" />
                        Logout
                    </Button>
                </div>
            </header>

            <main className="container mx-auto px-4 py-8">
                <h2 className="text-2xl font-bold mb-6">Market Sentiment</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {data.map((item) => {
                        const score = scores[item.ticker]
                        const decision = score?.decision || "neutral"

                        let decisionColor = "text-gray-500"
                        if (decision === "long") decisionColor = "text-green-600"
                        if (decision === "short") decisionColor = "text-red-600"

                        return (
                            <Card key={item.ticker}>
                                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                    <CardTitle className="text-lg font-medium">
                                        {item.ticker}
                                    </CardTitle>
                                    <div className={`text-sm font-bold uppercase ${decisionColor}`}>
                                        {decision}
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="text-2xl font-bold">
                                        {((score?.prob_up || 0) * 100).toFixed(1)}%
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Probability Up
                                    </p>

                                    <div className="mt-4 space-y-2">
                                        <div className="flex justify-between text-sm">
                                            <span>Sentiment Score:</span>
                                            <span className={item.mean_sent > 0 ? "text-green-600" : "text-red-600"}>
                                                {item.mean_sent.toFixed(2)}
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-sm">
                                            <span>Article Count:</span>
                                            <span>{item.count}</span>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )
                    })}
                </div>
            </main>
        </div>
    )
}
