Attribute VB_Name = "Module4"
Option Explicit


    Const num = 1 '成分数 - 1
    Const pi = 3.14159
    Const R = 8.31451 'Pa m3/(mol K)
    
    Const m = 100  '塔の分割数
    
    'Langmuirパラメータ
    Dim qmax(num) As Double
    Dim b(num) As Double
    
    Dim C0(num) As Double '初期濃度 kmol/m3
    Dim u0 As Double '空塔線速度
    Dim Tt As Double '吸着塔操作温度
    
    Dim qtz(num) As Double
    Dim Ct(num, 2000) As Double 'C_t(i, z)
    Dim qt(num, 2000) As Double 'q_t(i, z)
    Dim countrec As Integer
    Dim output_data_Cq(m, 4) As Double
    Dim FlowOut(num) As Double '非吸着出口から出て行った量
    Dim PurgeOut(num) As Double 'パージ出口から出て行った量
    Dim decompOut(num) As Double '減圧時のメモ用
    Dim endTime(1) As Double '吸着脱着終了時間

Sub main()

    With Application
        .Calculation = xlCalculationManual
        .EnableEvents = False
        .ScreenUpdating = False
    End With

    Call Adsorption_1
    Debug.Print ("吸着1 完了")
    
    Call Desorption
    Debug.Print ("脱着1 完了")
    
    Call Adsorption_2
    Debug.Print ("吸着2 完了")

    Call Desorption
    Debug.Print ("脱着2 完了")
    
    With Application
        .Calculation = xlCalculationAutomatic
        .EnableEvents = True
        .ScreenUpdating = True
    End With

End Sub


Sub Adsorption_1()
    Dim Ct_1(num, 2000) As Double 'C_t+1(i, z)
    Dim Ceq(num, 2000) As Double 'Ceq_t(i, z)
    Dim qt_1(num, 2000) As Double 'q_t+1(i, z)
    Dim Cin(num) '無次元初期濃度
    Dim qin(num) '無次元初期吸着量
    Dim t As Double
    Dim dt As Double
    Dim z As Double
    Dim dz As Double
    Dim flow(num) As Double 'モル流量 kmol/s
    Dim FAll As Double '全モル流量 kmol/s
    Dim V As Double '体積流量 m3/s
    Dim u(2000) As Double

    '偏微分方程式の係数
    Dim w As Double
    Dim f As Double
    Dim g(num) As Double
    Dim h(num) As Double

    Dim Pt As Double '吸着塔圧力 Pa
    Dim Lt As Double '塔高 m
    Dim S As Double '塔断面積 m2
    Dim DiaTower As Double '塔径 m
    Dim eps As Double '空隙率
    Dim Kfav(num) As Double '総括物質移動係数 1/s
    Dim rho As Double '気体密度 kg/m3
    Dim rho_ads As Double '充填塔密度 kg/m3
    Dim Mav As Double '平均分子量 kg/kmol
    Dim i As Integer, j As Integer, k As Integer, Count As Long
    
    Worksheets("塔内状況メモ1").Cells.Clear


    '定数入力
    eps = Worksheets("吸着材データ").Cells(3, 6).Value
    Pt = Worksheets("吸着塔設計").Cells(2, 6).Value * 1000 'Pa
    Mav = Worksheets("成分流量").Cells(11, 2).Value 'kg/kmol
    Tt = Worksheets("吸着塔設計").Cells(9, 6).Value 'K
    rho = Pt / R / Tt * Mav / 1000 'kg/m3
    u0 = Worksheets("吸着塔設計").Cells(7, 6).Value 'm/s
    Lt = Worksheets("吸着塔設計").Cells(6, 6).Value 'm
    rho_ads = Worksheets("吸着材データ").Cells(8, 6).Value 'kg/m3
    DiaTower = Worksheets("吸着塔設計").Cells(11, 6).Value 'm
    S = DiaTower * DiaTower * pi / 4

    u(0) = 1
    dt = 0.000005 '0.0001
    dz = 1 / m

    Dim input_data_Lang
    input_data_Lang = Worksheets("成分物性値").Range("B3:C4").Value
    For i = 0 To num
        qmax(i) = input_data_Lang(i + 1, 1) 'kmol/kg
        b(i) = input_data_Lang(i + 1, 2) / 1000 '1/Pa
    Next i

    '確認出力
    Dim output_data_Lang(num, 1) As Double
    For i = 0 To num
        output_data_Lang(i, 0) = qmax(i)
        output_data_Lang(i, 1) = b(i) * 1000 'kPa
    Next i
    Worksheets("成分物性値").Range("B8:C9").Value = output_data_Lang

    Dim input_data_Trans
    input_data_Trans = Worksheets("成分物性値").Range("L14:L15").Value
    
    For i = 0 To num
        Kfav(i) = input_data_Trans(i + 1, 1) '1/s
    Next i

    Dim input_data_f
        input_data_f = Worksheets("成分流量").Range("B2:B3").Value
    FAll = 0
    
    For i = 0 To num
        flow(i) = input_data_f(i + 1, 1) / 3600 'kmol/h -> kmol/s
        FAll = FAll + flow(i)
    Next i
    
    V = Worksheets("成分流量").Cells(10, 2).Value / 3600 'm3/h -> m3/s

    For i = 0 To num
        C0(i) = flow(i) / V 'kmol/m3
    Next i
    
    Worksheets("成分流量").Cells(2, 5) = C0(0)
    Worksheets("成分流量").Cells(3, 5) = C0(1)
    
    '入口ではC = 1, q = 0とする
    For i = 0 To num
        Cin(i) = 1
        qin(i) = 0
    Next i

    '偏微分係数
    f = -dt / eps / dz
    w = -(R * 1000) * Tt * Lt * dz / Pt / u0
    For i = 0 To num
        g(i) = Kfav(i) * dt * Lt / eps / u0
        h(i) = Kfav(i) * dt * Lt * C0(i) / rho_ads / u0 / qmax(i)
    Next i

    'z = 0より入口濃度を参照
    For i = 0 To num
        Ct(i, 0) = Cin(i)
        qt(i, 0) = qin(i)
    Next i
    
    Count = 1
    
    ' t = 0のとき 1回目はすべて0から始める
    For k = 1 To m
        For i = 0 To num
            Ct(i, k) = 0
            qt(i, k) = 0
        Next i
    Next k
    
    FlowOut(0) = 0
    FlowOut(1) = 0

    '初期状態出力
    countrec = 1
    For k = 1 To m
        For i = 0 To num
            output_data_Cq(k - 1, i) = C0(i) * Ct(i, k)
            output_data_Cq(k - 1, i + 2) = qmax(i) * qt(i, k)
        Next i
        Worksheets("塔内状況メモ1").Cells(k + 2, 1).Value = k * Lt * dz
    Next k
    Worksheets("塔内状況メモ1").Range(Worksheets("塔内状況メモ1").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ1").Cells(m + 2, 6 * countrec)) = output_data_Cq
    Worksheets("塔内状況メモ1").Cells(1, 6 * countrec - 4).Value = 0
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 4).Value = "C_H2"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 3).Value = "C_CH4"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 2).Value = "q_H2"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 1).Value = "q_CH4"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec).Value = "u"
    Debug.Print ("吸着1 " + Str(countrec))


    Do
        u(0) = 1
        For k = 1 To m
            For i = 0 To num
                qtz(i) = qt(i, k)
                Ct(i, 0) = Cin(i)
            Next i
            Ceq(0, k) = 0.001 / (R * Tt * b(0) * C0(0)) * qtz(0) / (1 - qtz(0) - qtz(1))
            Ceq(1, k) = 0.001 / (R * Tt * b(1) * C0(1)) * qtz(1) / (1 - qtz(0) - qtz(1))
            '空塔速度変化
            u(k) = w * (Kfav(0) * C0(0) * (Ct(0, k) - Ceq(0, k)) + Kfav(1) * C0(1) * (Ct(1, k) - Ceq(1, k))) + u(k - 1)
            For i = 0 To num
                '濃度変化
                Ct_1(i, k) = f * Ct(i, k) * (u(k) - u(k - 1)) + f * u(k) * (Ct(i, k) - Ct(i, k - 1)) - g(i) * (Ct(i, k) - Ceq(i, k)) + Ct(i, k)
                '吸着量変化
                qt_1(i, k) = h(i) * (Ct(i, k) - Ceq(i, k)) + qtz(i)
                If qt_1(i, k) < 0# Then
                    qt_1(i, k) = 0#
                End If
            Next i
            
            For i = 0 To num
                Ct(i, k) = Ct_1(i, k)
                qt(i, k) = qt_1(i, k)
            Next i
        
        Next k
    
        '5000 回で書き出し
        If Count Mod 50000 = 0 Then
            countrec = countrec + 1
            For k = 1 To m
                For i = 0 To num
                    output_data_Cq(k - 1, i) = C0(i) * Ct_1(i, k) 'kmol/m3
                    output_data_Cq(k - 1, i + 2) = qmax(i) * qt_1(i, k) 'kmol/kg
                Next i
                output_data_Cq(k - 1, 4) = u0 * u(k) 'm/s
            Next k
            Worksheets("塔内状況メモ1").Range(Worksheets("塔内状況メモ1").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ1").Cells(m + 2, 6 * countrec)) = output_data_Cq
            Worksheets("塔内状況メモ1").Cells(1, 6 * countrec - 4).Value = Count * Lt / u0 * dt
            Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 4).Value = "C_H2"
            Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 3).Value = "C_CH4"
            Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 2).Value = "q_H2"
            Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 1).Value = "q_CH4"
            Worksheets("塔内状況メモ1").Cells(2, 6 * countrec).Value = "u"
            Debug.Print ("吸着1 " + Str(countrec))
        End If
        
        Count = Count + 1
        
        For i = 0 To num
            FlowOut(i) = FlowOut(i) + C0(i) * Lt * dt * Ct_1(i, m) * u(m) * S
        Next i

    Loop Until Ct_1(1, m) > 0.05
    
    '破過データ書き出し
    countrec = countrec + 1
    endTime(0) = (Count - 1) * Lt / u0 * dt
    For k = 1 To m
        For i = 0 To num
            output_data_Cq(k - 1, i) = C0(i) * Ct_1(i, k)
            output_data_Cq(k - 1, i + 2) = qmax(i) * qt_1(i, k)
        Next i
        output_data_Cq(k - 1, 4) = u0 * u(k) 'm/s
    Next k
    Worksheets("塔内状況メモ1").Range(Worksheets("塔内状況メモ1").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ1").Cells(m + 2, 6 * countrec)) = output_data_Cq
    Worksheets("塔内状況メモ1").Cells(1, 6 * countrec - 4).Value = (Count - 1) * Lt / u0 * dt
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 4).Value = "C_H2"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 3).Value = "C_CH4"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 2).Value = "q_H2"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec - 1).Value = "q_CH4"
    Worksheets("塔内状況メモ1").Cells(2, 6 * countrec).Value = "u"
    Worksheets("成分流量").Cells(2, 6).Value = FlowOut(0)
    Worksheets("成分流量").Cells(3, 6).Value = FlowOut(1)
    Worksheets("成分流量").Cells(5, 6).Value = endTime(0)
    

End Sub


Sub Desorption()
    Dim Ct_1(num, 2000) As Double 'C_t+1(i, z)
    Dim Ceq(num, 2000) As Double 'Ceq_t(i, z)
    Dim qt_1(num, 2000) As Double 'q_t+1(i, z)
    Dim Cin(num) '無次元初期濃度
    Dim qin(num) '無次元初期吸着量
    Dim t As Double
    Dim dt As Double
    Dim z As Double
    Dim dz As Double
    Dim flow(num) As Double 'モル流量 kmol/s
    Dim FAll As Double '全モル流量 kmol/s
    Dim V As Double '体積流量 m3/s
    Dim u(2000) As Double

    '偏微分方程式の係数
    Dim w As Double
    Dim f As Double
    Dim g(num) As Double
    Dim h(num) As Double

    Dim Pt As Double '吸着塔圧力 Pa
    Dim Lt As Double '塔高 m
    Dim S As Double '塔断面積 m2
    Dim DiaTower As Double '塔径 m
    Dim eps As Double '空隙率
    Dim Kfav(num) As Double '総括物質移動係数 1/s
    Dim rho As Double '気体密度 kg/m3
    Dim rho_ads As Double '充填塔密度 kg/m3
    Dim Mav As Double '平均分子量 kg/kmol
    Dim i As Integer, j As Integer, k As Integer, Count As Long

    Worksheets("塔内状況メモ2").Cells.Clear

    '定数入力
    eps = Worksheets("吸着材データ").Cells(3, 6).Value
    Pt = Worksheets("吸着塔設計").Cells(3, 6).Value * 1000 'Pa
    Mav = Worksheets("成分流量").Cells(11, 2).Value 'kg/kmol
    Tt = Worksheets("吸着塔設計").Cells(9, 6).Value 'K
    rho = Pt / R / Tt * Mav / 1000 'kg/m3
    u0 = Worksheets("吸着塔設計").Cells(10, 6).Value 'm/s
    Lt = Worksheets("吸着塔設計").Cells(6, 6).Value 'm
    rho_ads = Worksheets("吸着材データ").Cells(8, 6).Value 'kg/m3
    DiaTower = Worksheets("吸着塔設計").Cells(11, 6).Value 'm
    S = DiaTower * DiaTower * pi / 4
    
    u(0) = 1
    dt = 0.000001 ' 0.000005
    dz = 1 / m


    Dim input_data_Trans
    input_data_Trans = Worksheets("成分物性値").Range("L17:L18").Value
    
    For i = 0 To num
        Kfav(i) = input_data_Trans(i + 1, 1) '1/s
    Next i
    
    '入口ではC = 吸着時の出口ガス組成, q = 0とする
    f = Pt / R / Tt / (FlowOut(0) + FlowOut(1)) / 1000
    For i = 0 To num
        Cin(i) = FlowOut(i) * f / C0(i)
        qin(i) = 0
    Next i
    
    Worksheets("成分流量").Cells(2, 7) = C0(0) * Cin(0)
    Worksheets("成分流量").Cells(3, 7) = C0(1) * Cin(1)
    
    '偏微分係数
    f = -dt / eps / dz
    w = -(R * 1000) * Tt * Lt * dz / Pt / u0
    For i = 0 To num
        g(i) = Kfav(i) * dt * Lt / eps / u0
        h(i) = Kfav(i) * dt * Lt * C0(i) / rho_ads / u0 / qmax(i)
    Next i

    'z = Ltより入口濃度を参照
    For i = 0 To num
        Ct(i, m + 1) = Cin(i)
        qt(i, m + 1) = qin(i)
    Next i
    
    Count = 1
    Dim kk As Integer
    PurgeOut(0) = 0
    PurgeOut(1) = 0

    '初期状態出力
    countrec = 1
    For k = 1 To m
        For i = 0 To num
            output_data_Cq(k - 1, i) = C0(i) * Ct(i, k)
            output_data_Cq(k - 1, i + 2) = qmax(i) * qt(i, k)
        Next i
        output_data_Cq(k - 1, 4) = 0
        Worksheets("塔内状況メモ2").Cells(k + 2, 1).Value = k * Lt * dz
    Next k
    Worksheets("塔内状況メモ2").Range(Worksheets("塔内状況メモ2").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ2").Cells(m + 2, 6 * countrec)) = output_data_Cq
    Worksheets("塔内状況メモ2").Cells(1, 6 * countrec - 4).Value = 0
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 4).Value = "C_H2"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 3).Value = "C_CH4"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 2).Value = "q_H2"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 1).Value = "q_CH4"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec).Value = "u"
    Debug.Print ("脱着 " + Str(countrec))
    
    Do
        u(m + 1) = 1
        For k = 1 To m
            kk = m + 1 - k
            For i = 0 To num
                qtz(i) = qt(i, kk)
            Next i
            Ceq(0, kk) = 0.001 / (R * Tt * b(0) * C0(0)) * qtz(0) / (1 - qtz(0) - qtz(1))
            Ceq(1, kk) = 0.001 / (R * Tt * b(1) * C0(1)) * qtz(1) / (1 - qtz(0) - qtz(1))
            '空塔速度変化
            u(kk) = u(kk + 1)
            'u(kk) = w * (Kfav(0) * C0(0) * (Ct(0, kk) - Ceq(0, kk)) + Kfav(1) * C0(1) * (Ct(1, kk) - Ceq(1, kk))) + u(kk + 1)
            For i = 0 To num
                '濃度変化
                'Ct_1(i, kk) = f * Ct(i, kk) * (u(kk) - u(kk + 1)) + f * u(kk) * (Ct(i, kk) - Ct(i, kk + 1)) - g(i) * (Ct(i, kk) - Ceq(i, kk)) + Ct(i, kk)
                Ct_1(i, kk) = f * u(kk) * (Ct(i, kk) - Ct(i, kk + 1)) - g(i) * (Ct(i, kk) - Ceq(i, kk)) + Ct(i, kk)
                '吸着量変化
                qt_1(i, kk) = h(i) * (Ct(i, kk) - Ceq(i, kk)) + qtz(i)
                If qt_1(i, kk) < 0# Then
                    qt_1(i, kk) = 0#
                End If
            Next i
            
            For i = 0 To num
                Ct(i, kk) = Ct_1(i, kk)
                qt(i, kk) = qt_1(i, kk)
            Next i
        
        Next k
    
        '100000 回で書き出し
        If Count Mod 300000 = 0 Then
            countrec = countrec + 1
            For k = 1 To m
                For i = 0 To num
                    output_data_Cq(k - 1, i) = C0(i) * Ct_1(i, k) 'kmol/m3
                    output_data_Cq(k - 1, i + 2) = qmax(i) * qt_1(i, k) 'kmol/kg
                Next i
                output_data_Cq(k - 1, 4) = u0 * u(k) 'm/s
            Next k
            Worksheets("塔内状況メモ2").Range(Worksheets("塔内状況メモ2").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ2").Cells(m + 2, 6 * countrec)) = output_data_Cq
            Worksheets("塔内状況メモ2").Cells(1, 6 * countrec - 4).Value = Count * Lt / u0 * dt
            Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 4).Value = "C_H2"
            Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 3).Value = "C_CH4"
            Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 2).Value = "q_H2"
            Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 1).Value = "q_CH4"
            Worksheets("塔内状況メモ2").Cells(2, 6 * countrec).Value = "u"
            Debug.Print ("脱着 " + Str(countrec))
        End If
        
        Count = Count + 1
        
        For i = 0 To num
            PurgeOut(i) = PurgeOut(i) + C0(i) * Lt * dt * Ct_1(i, 1) * u(1) * S
        Next i
        
    Loop Until qt_1(1, 1) < 0.005
    
    '破過データ書き出し
    countrec = countrec + 1
    endTime(1) = (Count - 1) * Lt / u0 * dt
    For k = 1 To m
        For i = 0 To num
            output_data_Cq(k - 1, i) = C0(i) * Ct_1(i, k)
            output_data_Cq(k - 1, i + 2) = qmax(i) * qt_1(i, k)
        Next i
        output_data_Cq(k - 1, 4) = u0 * u(k) 'm/s
    Next k
    Worksheets("塔内状況メモ2").Range(Worksheets("塔内状況メモ2").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ2").Cells(m + 2, 6 * countrec)) = output_data_Cq
    Worksheets("塔内状況メモ2").Cells(1, 6 * countrec - 4).Value = endTime(1)
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 4).Value = "C_H2"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 3).Value = "C_CH4"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 2).Value = "q_H2"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec - 1).Value = "q_CH4"
    Worksheets("塔内状況メモ2").Cells(2, 6 * countrec).Value = "u"
    Worksheets("成分流量").Cells(2, 8).Value = PurgeOut(0)
    Worksheets("成分流量").Cells(3, 8).Value = PurgeOut(1)
    Worksheets("成分流量").Cells(5, 8).Value = endTime(1)
    Worksheets("成分流量").Cells(2, 6).Value = FlowOut(0) - C0(0) * Cin(0) * u0 * S * endTime(1)
    Worksheets("成分流量").Cells(3, 6).Value = FlowOut(1) - C0(1) * Cin(1) * u0 * S * endTime(1)
    Worksheets("成分流量").Cells(5, 6).Value = endTime(0)
    

End Sub



Sub Adsorption_2()
    Dim Ct_1(num, 2000) As Double 'C_t+1(i, z)
    Dim Ceq(num, 2000) As Double 'Ceq_t(i, z)
    Dim qt_1(num, 2000) As Double 'q_t+1(i, z)
    Dim Cin(num) '無次元初期濃度
    Dim qin(num) '無次元初期吸着量
    Dim t As Double
    Dim dt As Double
    Dim z As Double
    Dim dz As Double
    Dim flow(num) As Double 'モル流量 kmol/s
    Dim FAll As Double '全モル流量 kmol/s
    Dim V As Double '体積流量 m3/s
    Dim u(2000) As Double

    '偏微分方程式の係数
    Dim w As Double
    Dim f As Double
    Dim g(num) As Double
    Dim h(num) As Double

    Dim Pt As Double '吸着塔圧力 Pa
    Dim Lt As Double '塔高 m
    Dim S As Double '塔断面積 m2
    Dim DiaTower As Double '塔径 m
    Dim eps As Double '空隙率
    Dim Kfav(num) As Double '総括物質移動係数 1/s
    Dim rho As Double '気体密度 kg/m3
    Dim rho_ads As Double '充填塔密度 kg/m3
    Dim Mav As Double '平均分子量 kg/kmol
    Dim i As Integer, j As Integer, k As Integer, Count As Long
    
    Worksheets("塔内状況メモ3").Cells.Clear


    '定数入力
    eps = Worksheets("吸着材データ").Cells(3, 6).Value
    Pt = Worksheets("吸着塔設計").Cells(2, 6).Value * 1000 'Pa
    Mav = Worksheets("成分流量").Cells(11, 2).Value 'kg/kmol
    Tt = Worksheets("吸着塔設計").Cells(9, 6).Value 'K
    rho = Pt / R / Tt * Mav / 1000 'kg/m3
    u0 = Worksheets("吸着塔設計").Cells(7, 6).Value 'm/s
    Lt = Worksheets("吸着塔設計").Cells(6, 6).Value 'm
    rho_ads = Worksheets("吸着材データ").Cells(8, 6).Value 'kg/m3
    DiaTower = Worksheets("吸着塔設計").Cells(11, 6).Value 'm
    S = DiaTower * DiaTower * pi / 4
    
    u(0) = 1
    dt = 0.000005 ' 0.0001
    dz = 1 / m

    Dim input_data_Trans
    input_data_Trans = Worksheets("成分物性値").Range("L14:L15").Value
    
    For i = 0 To num
        Kfav(i) = input_data_Trans(i + 1, 1) '1/s
    Next i
    
    '入口ではC = 1, q = 0とする
    For i = 0 To num
        Cin(i) = 1
        qin(i) = 0
    Next i

    '偏微分係数
    f = -dt / eps / dz
    w = -(R * 1000) * Tt * Lt * dz / Pt / u0
    For i = 0 To num
        g(i) = Kfav(i) * dt * Lt / eps / u0
        h(i) = Kfav(i) * dt * Lt * C0(i) / rho_ads / u0 / qmax(i)
    Next i

    'z = 0より入口濃度を参照
    For i = 0 To num
        Ct(i, 0) = Cin(i)
        qt(i, 0) = qin(i)
    Next i
    
    Count = 1
    FlowOut(0) = 0
    FlowOut(1) = 0
    
    '初期状態出力
    countrec = 1
    For k = 1 To m
        For i = 0 To num
            output_data_Cq(k - 1, i) = C0(i) * Ct(i, k)
            output_data_Cq(k - 1, i + 2) = qmax(i) * qt(i, k)
        Next i
        output_data_Cq(k - 1, 4) = 0
        Worksheets("塔内状況メモ3").Cells(k + 2, 1).Value = k * Lt * dz
    Next k
    Worksheets("塔内状況メモ3").Range(Worksheets("塔内状況メモ3").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ3").Cells(m + 2, 6 * countrec)) = output_data_Cq
    Worksheets("塔内状況メモ3").Cells(1, 6 * countrec - 4).Value = 0
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 4).Value = "C_H2"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 3).Value = "C_CH4"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 2).Value = "q_H2"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 1).Value = "q_CH4"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec).Value = "u"
    Debug.Print ("吸着2 " + Str(countrec))

    Do
        u(0) = 1
        For k = 1 To m
            For i = 0 To num
                qtz(i) = qt(i, k)
                Ct(i, 0) = Cin(i)
            Next i
            Ceq(0, k) = 0.001 / (R * Tt * b(0) * C0(0)) * qtz(0) / (1 - qtz(0) - qtz(1))
            Ceq(1, k) = 0.001 / (R * Tt * b(1) * C0(1)) * qtz(1) / (1 - qtz(0) - qtz(1))
            '空塔速度変化
            u(k) = w * (Kfav(0) * C0(0) * (Ct(0, k) - Ceq(0, k)) + Kfav(1) * C0(1) * (Ct(1, k) - Ceq(1, k))) + u(k - 1)
            For i = 0 To num
                '濃度変化
                Ct_1(i, k) = f * Ct(i, k) * (u(k) - u(k - 1)) + f * u(k) * (Ct(i, k) - Ct(i, k - 1)) - g(i) * (Ct(i, k) - Ceq(i, k)) + Ct(i, k)
                '吸着量変化
                qt_1(i, k) = h(i) * (Ct(i, k) - Ceq(i, k)) + qtz(i)
                If qt_1(i, k) < 0# Then
                    qt_1(i, k) = 0#
                End If
            Next i
            
            For i = 0 To num
                Ct(i, k) = Ct_1(i, k)
                qt(i, k) = qt_1(i, k)
            Next i
        
        Next k
    
        '5000 回で書き出し
        If Count Mod 250000 = 0 Then
            countrec = countrec + 1
            For k = 1 To m
                For i = 0 To num
                    output_data_Cq(k - 1, i) = C0(i) * Ct_1(i, k) 'kmol/m3
                    output_data_Cq(k - 1, i + 2) = qmax(i) * qt_1(i, k) 'kmol/kg
                Next i
                output_data_Cq(k - 1, 4) = u0 * u(k) 'm/s
            Next k
            Worksheets("塔内状況メモ3").Range(Worksheets("塔内状況メモ3").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ3").Cells(m + 2, 6 * countrec)) = output_data_Cq
            Worksheets("塔内状況メモ3").Cells(1, 6 * countrec - 4).Value = Count * Lt / u0 * dt
            Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 4).Value = "C_H2"
            Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 3).Value = "C_CH4"
            Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 2).Value = "q_H2"
            Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 1).Value = "q_CH4"
            Worksheets("塔内状況メモ3").Cells(2, 6 * countrec).Value = "u"
            Debug.Print ("吸着2 " + Str(countrec))
        End If
        
        Count = Count + 1
        
        For i = 0 To num
            FlowOut(i) = FlowOut(i) + C0(i) * Lt * dt * Ct_1(i, m) * u(m) * S
        Next i

    Loop Until Ct_1(1, m) > 0.05
    
    '破過データ書き出し
    countrec = countrec + 1
    endTime(0) = (Count - 1) * Lt / u0 * dt
    For k = 1 To m
        For i = 0 To num
            output_data_Cq(k - 1, i) = C0(i) * Ct_1(i, k)
            output_data_Cq(k - 1, i + 2) = qmax(i) * qt_1(i, k)
        Next i
        output_data_Cq(k - 1, 4) = u0 * u(k) 'm/s
    Next k
    Worksheets("塔内状況メモ3").Range(Worksheets("塔内状況メモ3").Cells(3, 6 * countrec - 4), Worksheets("塔内状況メモ3").Cells(m + 2, 6 * countrec)) = output_data_Cq
    Worksheets("塔内状況メモ3").Cells(1, 6 * countrec - 4).Value = (Count - 1) * Lt / u0 * dt
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 4).Value = "C_H2"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 3).Value = "C_CH4"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 2).Value = "q_H2"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec - 1).Value = "q_CH4"
    Worksheets("塔内状況メモ3").Cells(2, 6 * countrec).Value = "u"
    Worksheets("成分流量").Cells(2, 6).Value = FlowOut(0)
    Worksheets("成分流量").Cells(3, 6).Value = FlowOut(1)
    Worksheets("成分流量").Cells(5, 6).Value = endTime(0)
    
End Sub

