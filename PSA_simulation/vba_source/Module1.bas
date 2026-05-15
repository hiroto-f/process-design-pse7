Attribute VB_Name = "Module1"
Option Explicit


Const H2 = 0
Const CH4 = 1

Const num = 1 '成分数 - 1
Const pi = 3.14159
Const R = 8.31451

'混合気体の密度計算で使う変数
Dim ek(num) As Double 'ε/κ K
Dim mu(num) As Double '各成分粘度 kg/(m・s)
Dim mumix As Double '混合気体粘度 kg/(m・s)
Dim m(num) As Double '分子量 g/mol
Dim sigma(num) As Double '衝突直径 Å
Dim x(num) As Double '組成比
'拡散係数
Dim Dai(num, num, 1) As Double '2成分間拡散係数 m2/s
Dim Dam(num, 1) As Double '他成分に対する拡散係数 m2/s
Dim Dkai(num, 1) As Double 'ミクロ孔Knudsen拡散 m2/s
Dim Dkaa(num, 1) As Double 'マクロ孔Knudsen拡散 m2/s
Dim Dea(num, 1) As Double '粒子内総括拡散係数 m2/s
'充填物データ
Dim ri As Double 'ミクロ孔半径 m
Dim ra As Double 'マクロ孔半径 m
Dim epsi As Double 'ミクロ孔空隙率
Dim epsa As Double 'マクロ孔空隙率
Dim av As Double '吸着材比表面積 m2/m3
Dim dp As Double '吸着材粒径 m
Dim eps As Double '空隙率
'混合気体の状態
Dim Mav As Double '混合気体平均分子量 g/mol
Dim rho As Double '気体密度 kg/m3
Dim u As Double '線速度 m/s
Dim Kfav(num, 1) As Double '総括物質移動係数 1/s
'塔設計
Dim Zt As Double '塔高 m
Dim Dto As Double '塔径 m
Dim Zt_Dto As Double '塔高/塔径
Dim rho_ads As Double '吸着材密度 kg/m3

Dim i As Integer, j As Integer, ii As Integer
Dim hd As Double '塔高/塔径
Dim Tt As Double '操作温度 K
Dim Pt As Double '塔操作圧力 kPa
Dim Phigh As Double '高圧力 kPa
Dim Plow As Double '低圧力 kPa
Dim uhigh As Double '吸着時線速度 m/s
Dim ulow As Double '脱着時線速度 m/s
Dim qt As Double '流入モル流量 mol/s
Dim Vt As Double '流入体積流量 m3/s
Dim reflux As Double '再生係数　脱着入口への再生/吸着出口

'HYSYS接続
Dim hyCase As SimulationCase
Dim hyFS As Object
Dim hyStream As ProcessStream
Dim xlsFS As Worksheet


Sub SetUp()

    Call From_HYSYS
    Call Adsorption_Data_Load
    Call Tower_Data_Load
    Call Mix_Viscosity
    Call Diffusion_Coef
    Call Mass_Transfer

End Sub




Sub From_HYSYS()

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    Set hyCase = GetObject("C:\Users\a7016\OneDrive - Kyoto University\プロセス設計\HYSYS\Sabatier 0604.hsc")
    Set hyFS = hyCase.Flowsheet

    Dim f(1) As ProcessStream
    
    
    Dim fi(5) As Double 'モル流量
    Dim FAll As Double '全モル流量
    Dim f2 As Double '2成分流量
    Dim xi(5) As Double '入口モル分率
    Dim xi2(num) As Double '2成分モル分率
    
    'HYSYSから読み込み
    Set flow(1) = hyCase.Flowsheet.MaterialStreams.Item("to PSA")
    
    'モル流量入力
    fi(H2) = f(1).ComponentMolarFlow(4) * 3600 'H2 kmol/h
    fi(CH4) = f(1).ComponentMolarFlow(11) * 3600 'CH4
    fi(2) = f(1).ComponentMolarFlow(3) * 3600 'B
    fi(3) = f(1).ComponentMolarFlow(2) * 3600 'T
    fi(4) = f(1).ComponentMolarFlow(1) * 3600 'S
    fi(5) = f(1).ComponentMolarFlow(0) * 3600 'EB
    
    FAll = 0
    f2 = 0
    For i = 0 To 5
        FAll = FAll + fi(i) 'kmol/h
    Next
    For i = 0 To num
        f2 = f2 + fi(i) 'kmol/h
    Next
    
    'モル分率計算
    For i = 0 To 5
        xi(i) = fi(i) / FAll
    Next
    For i = 0 To num
        xi2(i) = fi(i) / f2
    Next
    
    'ワークシート出力
    Dim output_data_flow(5, 2) As Double
    For i = 0 To 5
        output_data_flow(i, 0) = fi(i)
        output_data_flow(i, 1) = xi(i)
        If i <= num Then
            output_data_flow(i, 2) = xi2(i)
        End If
    Next
    
    f(1).PressureValue = Worksheets("吸着塔設計").Cells(2, 2).Value
    f(1).TemperatureValue = Worksheets("吸着塔設計").Cells(4, 2).Value
    
    Worksheets("成分流量").Range("B2:D7").Value = output_data_flow
    Worksheets("成分流量").Cells(8, 2).Value = f(1).Temperature + 273.15
    Worksheets("成分流量").Cells(9, 2).Value = f(1).PressureValue
    Worksheets("成分流量").Cells(10, 2).Value = f(1).ActualVolumeFlow * 3600

    'モジュール変数出力
    For i = 0 To num
        x(i) = xi2(i)
    Next
    qt = f2 / 3.6 'kmol/h -> mol/s
    Tt = t(1).Temperature + 273.15 '℃ -> K
    Vt = V(1).ActualVolumeFlow 'm3/h -> m3/s

    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True


End Sub

Sub Mix_Viscosity()

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    Dim Tn As Double 'Ωを計算するときのT*
    Dim omega As Double '衝突積分Ω

    For i = 0 To num
        Tn = Tt / ek(i)
        omega = 1.16145 / (Tn ^ 0.14874) + 0.52487 / (Exp(0.7732 * Tn)) + 2.16178 / (Exp(2.43787 * Tn))
        mu(i) = (0.0000026693 * ((m(i) * Tt) ^ (0.5)) / sigma(i) / sigma(i) / omega)  'kg/(m・s)
    Next i

    'Wilke式
    Dim psi(num, num) As Double
    For i = 0 To num
        For j = 0 To num
            psi(i, j) = 1 / (8 ^ 0.5) / ((1 + m(i) / m(j)) ^ 0.5) * (1 + ((mu(i) / mu(j)) ^ 0.5) * ((m(j) / m(i)) ^ 0.25)) ^ 2
        Next j
    Next i

    Dim denom As Double
    mumix = 0
    For i = 0 To num
        denom = 0
        For j = 0 To num
            denom = denom + x(j) * psi(i, j)
        Next j
        mumix = mumix + x(i) * mu(i) / denom 'kg/(m・s)
    Next i

    '確認出力
    Dim output_data_mupsi(num, 2) As Double
    For i = 0 To num
        output_data_mupsi(i, 0) = mu(i)
        output_data_mupsi(i, 1) = psi(i, H2)
        output_data_mupsi(i, 2) = psi(i, CH4)
    Next
    Worksheets("成分物性値").Range("B14:D15").Value = output_data_mupsi
    Worksheets("成分物性値").Cells(16, 2).Value = mumix
    
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True

End Sub


Sub Adsorption_Data_Load()

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    '吸着材データ入力
    Dim input_data_ads
    input_data_ads = Worksheets("吸着材データ").Range("B2:B8").Value
    dp = input_data_ads(1, 1) 'm
    eps = input_data_ads(2, 1)
    epsa = input_data_ads(3, 1)
    epsi = input_data_ads(4, 1)
    ra = input_data_ads(5, 1) 'm
    ri = input_data_ads(6, 1) 'm
    rho_ads = input_data_ads(7, 1)
    av = 6 * (1 - eps) / dp 'kg/m3
    '入力確認
    Dim output_data_ads(7, 0) As Double
    output_data_ads(0, 0) = dp
    output_data_ads(1, 0) = eps
    output_data_ads(2, 0) = epsa
    output_data_ads(3, 0) = epsi
    output_data_ads(4, 0) = ra
    output_data_ads(5, 0) = ri
    output_data_ads(6, 0) = rho_ads
    output_data_ads(7, 0) = av
    Worksheets("吸着材データ").Range("F2:F9").Value = output_data_ads

    '成分物性値入力
    Dim input_data_comp
    input_data_comp = Worksheets("成分物性値").Range("F3:H4").Value
    For i = 0 To num
        m(i) = input_data_comp(i + 1, 1) 'g/mol
        ek(i) = input_data_comp(i + 1, 2) 'K
        sigma(i) = input_data_comp(i + 1, 3) 'Å
    Next

    '平均分子量
    Mav = 0
    For i = 0 To num
        Mav = Mav + x(i) * m(i) 'g/mol
    Next

    '入力確認
    Dim output_data_comp(num, 2) As Double
    For i = 0 To num
        output_data_comp(i, 0) = m(i)
        output_data_comp(i, 1) = ek(i)
        output_data_comp(i, 2) = sigma(i)
    Next
    Worksheets("成分物性値").Range("F8:H9").Value = output_data_comp
    Worksheets("成分流量").Cells(11, 2).Value = Mav

    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True

End Sub

Sub Tower_Data_Load()
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual


    '塔データ入力
    Dim input_data_tower
    input_data_tower = Worksheets("吸着塔設計").Range("B2:B8").Value

    Phigh = input_data_tower(1, 1) 'kPa
    Plow = input_data_tower(2, 1) 'kPa
    Zt_Dto = input_data_tower(5, 1)
    uhigh = input_data_tower(6, 1) 'm/s
    ulow = input_data_tower(7, 1) 'm/s
    
    Dto = (4 * Vt / uhigh / pi) ^ 0.5 'm
    Zt = Zt_Dto * Dto 'm
    reflux = ulow * Phigh / uhigh / Plow

    '確認出力
    Dim output_data_tower(10, 0) As Double
    output_data_tower(0, 0) = Phigh
    output_data_tower(1, 0) = Plow
    output_data_tower(4, 0) = Zt
    output_data_tower(5, 0) = uhigh
    output_data_tower(6, 0) = reflux
    output_data_tower(7, 0) = Tt
    output_data_tower(8, 0) = ulow
    output_data_tower(9, 0) = Dto
    output_data_tower(10, 0) = qt

    Worksheets("吸着塔設計").Range("F2:F12").Value = output_data_tower

    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True

End Sub



Sub Diffusion_Coef()

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    Dim Tn(num) As Double ''Ωを計算するときのT*
    Dim omega(num) As Double '衝突積分Ω
    Dim sigmaD(num, num) As Double '2成分間での衝突直径 Å
    Dim ekD(num, num) As Double '2成分間でのε/κ K
    Dim PP As Double '各操作時の圧力 kPa

    For ii = 0 To 1

        If ii = 0 Then
            PP = Phigh
        Else
            PP = Plow
        End If

        For i = 0 To num
            For j = 0 To num
                sigmaD(i, j) = (sigma(i) + sigma(j)) / 2
                ekD(i, j) = (ek(i) * ek(j)) ^ 0.5
                Tn(i) = Tt / ekD(i, j)
                omega(i) = 1.06036 / (Tn(i) ^ 0.1561) + 0.193 / (Exp(0.47635 * Tn(i))) + 1.03587 / (Exp(1.52996 * Tn(i))) + 1.76474 / (Exp(3.89411 * Tn(i)))
                '2成分間での拡散係数
                Dai(i, j, ii) = 0.0018583 * ((Tt * Tt * Tt * (1 / m(i) + 1 / m(j))) ^ 0.5) / (PP * 0.00986923 * sigmaD(i, j) * sigmaD(i, j) * omega(i))
                Dai(i, j, ii) = Dai(i, j, ii) / 10000 'cm2/s -> m2/s
            Next j

            '混合気体中の他成分に対する拡散係数
            Dam(i, ii) = 0
            For j = 0 To num
                If i <> j Then
                    Dam(i, ii) = Dam(i, ii) + x(j) / Dai(i, j, ii)
                End If
            Next j
            Dam(i, ii) = 1 / Dam(i, ii) 'm2/s

            'Knudsen拡散係数
            Dkaa(i, ii) = 3.067 * ra * ((Tt / (m(i) / 1000)) ^ 0.5) 'm2/s
            Dkai(i, ii) = 3.067 * ri * ((Tt / (m(i) / 1000)) ^ 0.5) 'm2/s

            '粒子内総括拡散係数 m2/s
            Dea(i, ii) = epsi * epsi * (1 + 3 * epsa) / (1 - epsa) / (1 / Dkai(i, ii) + 1 / Dam(i, ii)) + epsa * epsa / (1 / Dkaa(i, ii) + 1 / Dam(i, ii))
        Next i
    Next ii

    '確認出力
    Dim output_data_Diff(num, 4) As Double
    For i = 0 To num
        For j = 0 To num
            If i <> j Then
                output_data_Diff(i, j) = Dai(i, j, 0)
            End If
        Next j
        output_data_Diff(i, 2) = Dkai(i, 0)
        output_data_Diff(i, 3) = Dkaa(i, 0)
        output_data_Diff(i, 4) = Dea(i, 0)
    Next i
    Worksheets("成分物性値").Range("E14:I15").Value = output_data_Diff

    For i = 0 To num
        For j = 0 To num
            If i <> j Then
                output_data_Diff(i, j) = Dai(i, j, 1)
            End If
        Next j
        output_data_Diff(i, 2) = Dkai(i, 1)
        output_data_Diff(i, 3) = Dkaa(i, 1)
        output_data_Diff(i, 4) = Dea(i, 1)
    Next i
    Worksheets("成分物性値").Range("E17:I18").Value = output_data_Diff
    
    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True

End Sub

Sub Mass_Transfer()

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    Dim kf As Double '境膜での物質移動係数 m/s
    Dim mka As Double '粒子内での物質移動係数 1/s
    Dim output_data_Trans1(num, 2) As Double
    Dim output_data_Trans2(num, 2) As Double
    
    '吸着
    rho = (Phigh * 1000) / R / Tt * Mav * 0.001 'kg/m3
    u = uhigh
        
    For i = 0 To num
        'Carberry式
        kf = 1.15 * u / eps * ((mumix / rho / Dam(i, 0)) ^ (-2 / 3)) * ((u * dp * rho / mumix / eps) ^ (-0.5)) 'm/s
        mka = 60 * Dea(i, 0) * (1 - eps) / dp / dp '1/s
        '総括物質移動係数
        Kfav(i, 0) = 1 / (1 / (kf * av) + 1 / mka) '1/s

        output_data_Trans1(i, 0) = kf * av '1/s
        output_data_Trans1(i, 1) = mka
        output_data_Trans1(i, 2) = Kfav(i, 0)
    Next i

    '確認出力
    Worksheets("成分物性値").Range("J14:L15").Value = output_data_Trans1

    '脱着
    rho = (Plow * 1000) / R / Tt * Mav * 0.001 'kg/m3
    u = ulow
        
    For i = 0 To num
        'Carberyy式
        kf = 1.15 * u / eps * ((mumix / rho / Dam(i, 1)) ^ (-2 / 3)) * ((u * dp * rho / mumix / eps) ^ (-0.5)) 'm/s
        mka = 60 * Dea(i, 1) * (1 - eps) / dp / dp '1/s
        '総括物質移動係数
        Kfav(i, 1) = 1 / (1 / (kf * av) + 1 / mka) '1/s

        output_data_Trans2(i, 0) = kf * av '1/s
        output_data_Trans2(i, 1) = mka
        output_data_Trans2(i, 2) = Kfav(i, 1)
    Next i

    '確認出力
    Worksheets("成分物性値").Range("J17:L18").Value = output_data_Trans2

    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True

End Sub


Sub To_HYSYS()

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    
    Dim Xf(4) As Double
    Dim FlowFin As Double

    Set hyCase = GetObject("F:\forAspen\dealkylation2.hsc")
    Set hyFS = hyCase.Flowsheet.MaterialStreams
    Set xlsFS = Worksheets("成分流量")
    
    FlowFin = 0
    For i = 0 To 4
        FlowFin = FlowFin + xlsFS.Cells(i + 2, 14)
    Next
    For i = 0 To 4
        Xf(i) = xlsFS.Cells(i + 2, 14) / FlowFin
    Next
    
    '非吸着成分
    hyFS.Item("from PSA H2").MolarFlow.SetValue FlowFin / 3600
    hyFS.Item("from PSA H2").Temperature.SetValue Worksheets("吸着塔設計").Cells(9, 6).Value - 273.15
    hyFS.Item("from PSA H2").Pressure.SetValue Worksheets("吸着塔設計").Cells(2, 6).Value
    hyFS.Item("from PSA H2").ComponentMolarFraction.SetValues Xf()

    FlowFin = 0
    For i = 0 To 4
        FlowFin = FlowFin + xlsFS.Cells(i + 2, 15)
    Next
    For i = 0 To 4
        Xf(i) = xlsFS.Cells(i + 2, 15) / FlowFin
    Next
    
    '吸着成分
    hyFS.Item("from PSA OffGas").MolarFlow.SetValue FlowFin / 3600
    hyFS.Item("from PSA OffGas").Temperature.SetValue Worksheets("吸着塔設計").Cells(9, 6).Value - 273.15
    hyFS.Item("from PSA OffGas").Pressure.SetValue Worksheets("吸着塔設計").Cells(3, 6).Value
    hyFS.Item("from PSA OffGas").ComponentMolarFraction.SetValues Xf()
        
    Debug.Print ("データ渡し完了")

    Application.Calculation = xlCalculationAutomatic
    Application.ScreenUpdating = True


End Sub






