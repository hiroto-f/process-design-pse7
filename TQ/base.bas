Option Explicit

Dim Th1(500) As Double, Th2(500) As Double, qh1(500) As Double, Th(500) As Double, Qh(500) As Double
Dim Tl1(500) As Double, Tl2(500) As Double, ql1(500) As Double, Tl(500) As Double, Ql(500) As Double
Dim dTh(500) As Double, dTl(500) As Double, dThl(500) As Double
Dim forTGC(500) As Double, TGC(500) As Double, GCC(500) As Double, GCCmin As Double
Dim TGCThmin As Double, TGCTcmax As Double
Dim i As Integer, j As Long, NHdata As Integer, NLdata As Integer, GCdata As Integer
Dim MINdT As Double, minTh As Double, shiftQ As Double
Sub TQDiagram()
Dim Col_Qex As Integer, Col_Qen As Integer, Col_Data As Integer, Col_Cal As Integer

With ActiveSheet

    .Range("W4:AE100").ClearContents

    Col_Data = 3
    Col_Qex = 7
    Col_Qen = 15
    Col_Cal = 23

    .Range("F4:K43").Sort Key1:=.Range("I4"), Order1:=xlAscending, Header:=xlNo
    .Range("N4:S43").Sort Key1:=.Range("O4"), Order1:=xlAscending, Header:=xlNo

NHdata = .Cells(3, Col_Data).Value
NLdata = .Cells(4, Col_Data).Value
MINdT = .Cells(5, Col_Data).Value

For i = 1 To NHdata
    Th2(i) = .Cells(i + 3, Col_Qex).Value
    Th1(i) = .Cells(i + 3, Col_Qex + 2).Value
    If Th2(i) < Th1(i) Then
        MsgBox "The hot stream temperature input is invalid." & vbCrLf & "The outlet temperature must be less than or equal to the inlet temperature.", vbCritical
        Exit Sub
    End If
    qh1(i) = .Cells(i + 3, Col_Qex + 3).Value
    .Cells(2 * i + 2, Col_Cal + 4) = Th1(i)
    .Cells(2 * i + 3, Col_Cal + 4) = Th2(i)
Next i

For i = 1 To NLdata
    Tl1(i) = .Cells(i + 3, Col_Qen).Value
    Tl2(i) = .Cells(i + 3, Col_Qen + 2).Value
    If Tl2(i) < Tl1(i) Then
        MsgBox "The cold stream temperature input is invalid." & vbCrLf & "The outlet temperature must be greater than or equal to the inlet temperature.", vbCritical
        Exit Sub
    End If
    ql1(i) = .Cells(i + 3, Col_Qen + 3).Value
    .Cells(2 * i + 2, Col_Cal + 7) = Tl1(i)
    .Cells(2 * i + 3, Col_Cal + 7) = Tl2(i)
Next i

    .Range("AA4:AA100").Sort Key1:=.Range("AA4"), Order1:=xlAscending, Header:=xlNo
    .Range("AD4:AD100").Sort Key1:=.Range("AD4"), Order1:=xlAscending, Header:=xlNo

For i = 1 To NHdata * 2
    Th(i) = .Cells(i + 3, Col_Cal + 4).Value
    forTGC(i) = Th(i)
Next i

For i = 1 To NLdata * 2
    Tl(i) = .Cells(i + 3, Col_Cal + 7).Value
    forTGC(NHdata * 2 + i) = Tl(i) + MINdT
Next i

TGCThmin = .Cells(4, Col_Cal + 4).Value
TGCTcmax = .Cells(3 + NLdata * 2, Col_Cal + 7).Value

Qh(1) = 0
.Cells(4, Col_Cal + 5).Value = Qh(1)
For i = 2 To NHdata * 2
    Qh(i) = Qh(i - 1)
    If Th(i) <> Th(i - 1) Then
        For j = 1 To NHdata
            If (Th1(j) <> Th2(j)) And (Th(i) > Th1(j)) And (Th(i) <= Th2(j)) Then
                Qh(i) = Qh(i) + qh1(j) / (Th2(j) - Th1(j)) * (Th(i) - Th(i - 1))
            End If
        Next j
    ElseIf Th(i) = Th(i - 1) Then
        For j = 1 To NHdata
            If (Th1(j) = Th2(j)) And (Th1(j) = Th(i)) Then
                Qh(i) = Qh(i) + qh1(j)
            End If
        Next j
    End If
    .Cells(i + 3, Col_Cal + 5).Value = Qh(i)
Next i

Ql(1) = 0
.Cells(4, Col_Cal + 8).Value = Ql(1)
For i = 2 To NLdata * 2
    Ql(i) = Ql(i - 1)
    If Tl(i) <> Tl(i - 1) Then
    For j = 1 To NLdata
        If (Tl1(j) <> Tl2(j)) And (Tl(i) > Tl1(j)) And (Tl(i) <= Tl2(j)) Then
        Ql(i) = Ql(i) + ql1(j) / (Tl2(j) - Tl1(j)) * (Tl(i) - Tl(i - 1))
        End If
    Next j
    ElseIf Tl(i) = Tl(i - 1) Then
    For j = 1 To NLdata
        If (Tl1(j) = Tl2(j)) And (Tl1(j) = Tl(i)) Then
        Ql(i) = Ql(i) + ql1(j)
        End If
    Next j
    End If
    .Cells(i + 3, Col_Cal + 8).Value = Ql(i)
Next i

For i = 1 To NLdata * 2 + NHdata * 2
    .Cells(i + 3, Col_Cal).Value = forTGC(i)
Next i

.Range("W4:W100").Sort Key1:=.Range("W4"), Order1:=xlDescending, Header:=xlNo

j = 1
For i = 1 To NLdata * 2 + NHdata * 2
    forTGC(i) = .Cells(i + 3, Col_Cal).Value
    If j = 1 Then
        TGC(j) = forTGC(i)
        j = j + 1
    ElseIf forTGC(i) <> forTGC(i - 1) Then
        TGC(j) = forTGC(i)
        j = j + 1
    End If
Next i
GCdata = j - 1

.Range("W4:W100").ClearContents
Dim sen As Integer, sennetsu As Integer
sen = 0
sennetsu = 0
For j = 1 To GCdata + sen - 1
dTh(j) = 0
dTl(j) = 0
    For i = 1 To NHdata
        If Th2(i) <> Th1(i) And Th2(i) = TGC(j) Then
            dTh(j) = dTh(j) + (Th2(i) - TGC(j + 1)) / (Th2(i) - Th1(i)) * qh1(i)
        ElseIf Th2(i) = Th1(i) And Th2(i) = TGC(j) Then
            dTh(j) = dTh(j) + qh1(i)
            .Cells(j + sen + 3, Col_Cal).Value = TGC(j)
            sennetsu = 1
        ElseIf Th2(i) > TGC(j) And Th1(i) < TGC(j) Then
            dTh(j) = dTh(j) + (TGC(j) - TGC(j + 1)) / (Th2(i) - Th1(i)) * qh1(i)
        End If
    Next i
    For i = 1 To NLdata
        If Tl2(i) <> Tl1(i) And Tl2(i) + MINdT = TGC(j) Then
            dTl(j) = dTl(j) + (Tl2(i) + MINdT - TGC(j + 1)) / (Tl2(i) - Tl1(i)) * ql1(i)
        ElseIf Tl2(i) = Tl1(i) And Tl2(i) + MINdT = TGC(j) Then
            dTl(j) = dTl(j) + ql1(i)
            .Cells(j + sen + 3, Col_Cal).Value = TGC(j)
            sennetsu = 1
        ElseIf Tl2(i) + MINdT > TGC(j) And Tl1(i) + MINdT < TGC(j) Then
            dTl(j) = dTl(j) + (TGC(j) - TGC(j + 1)) / (Tl2(i) - Tl1(i)) * ql1(i)
        End If
    Next i
    If sennetsu = 0 Then
        dThl(j) = dTh(j) - dTl(j)
    Else
        dThl(j) = dTh(j) - dTl(j)
        .Cells(j + sen + 3, Col_Cal + 1).Value = dThl(j)
        sen = sen + 1
        dThl(j) = 0
        sennetsu = 0
    End If
    .Cells(j + sen + 3, Col_Cal).Value = TGC(j)
    .Cells(j + sen + 3, Col_Cal + 1).Value = dThl(j)
Next j

Dim Gccmin2 As Double, minth2 As Double, hasGccmin2 As Boolean
GCCmin = 0
minTh = 0
minth2 = 0
hasGccmin2 = False
GCC(0) = 0
For j = 1 To GCdata + sen - 2
    If TGC(j + 1) >= TGCThmin And TGC(j + 1) <= TGCTcmax + MINdT Then
        GCC(j) = GCC(j - 1) + .Cells(j + 3, Col_Cal + 1).Value
        If GCC(j) <= GCCmin Then
            GCCmin = GCC(j)
            minTh = .Cells(3 + j + 1, Col_Cal).Value
        End If
        If minTh = 0 And GCC(j) <= GCC(j - 1) Then
            Gccmin2 = GCC(j)
            minth2 = .Cells(3 + j + 1, Col_Cal).Value
            hasGccmin2 = True
        End If
    Else
        GCC(j) = GCC(j - 1) + .Cells(j + 3, Col_Cal + 1).Value
    End If
Next j

If minTh = 0 Then
    If hasGccmin2 Then
        minTh = minth2
        GCCmin = Gccmin2
    Else
        minTh = Tl(NLdata * 2) + MINdT
        GCCmin = dThl(1)
    End If
    GCC(0) = -GCC(1)
Else
    GCC(0) = 0
End If

For j = 0 To GCdata + sen - 2
    .Cells(j + 4, Col_Cal + 2).Value = GCC(j) + Abs(GCCmin)
Next j

Dim shift As Integer
shift = 0
shiftQ = 0
For i = 1 To NHdata * 2
    If minTh = Th(i) Then
    For j = 1 To NLdata * 2 - 1
        If Tl(j + 1) <> Tl(j) And Tl(j) <= minTh - MINdT And minTh - MINdT < Tl(j + 1) Then
            shiftQ = Qh(i) - Ql(j) + (Tl(j) + MINdT - Th(i)) * (Ql(j + 1) - Ql(j)) / (Tl(j + 1) - Tl(j))
            shift = 1
                Exit For
        End If
    Next j
    End If
Next i

If shift <> 1 Then
For i = 1 To NLdata * 2
    If minTh - MINdT = Tl(i) Then
    For j = 1 To NHdata * 2 - 1
        If Th(j + 1) <> Th(j) And Th(j) <= minTh And minTh < Th(j + 1) Then
            shiftQ = Qh(j) - Ql(i) + (Tl(i) + MINdT - Th(j)) * (Qh(j + 1) - Qh(j)) / (Th(j + 1) - Th(j))
                Exit For
        End If
    Next j
    End If
Next i
End If

Dim iii As Integer, jjj  As Integer, count As Integer, du As Double
Dim ThAll(20000) As Double, TlAll(20000) As Double

ThAll(0) = Th(1)
count = 1
For i = 1 To 20000
    du = i
    If count + 1 > NHdata * 2 Then
        Exit For
    End If
    If Qh(count + 1) <> Qh(count) And du * 0.1 <= Qh(count + 1) Then
        ThAll(i) = Th(count) + (Th(count + 1) - Th(count)) * (du * 0.1 - Qh(count)) / (Qh(count + 1) - Qh(count))
    End If
    Do
        If count + 1 > NHdata * 2 Then
            Exit For
        End If
        If (du + 1#) / 10# > Qh(count + 1) Then
            count = count + 1
        Else
            Exit Do
        End If
    Loop
Next i

TlAll(0) = Tl(1)
count = 1
For i = 1 To 20000
    du = i
    If count + 1 > NLdata * 2 Then
        Exit For
    End If
    If Ql(count + 1) <> Ql(count) And du * 0.1 <= Ql(count + 1) Then
        TlAll(i) = Tl(count) + (Tl(count + 1) - Tl(count)) * (du * 0.1 - Ql(count)) / (Ql(count + 1) - Ql(count))
    End If
    Do
        If count + 1 > NLdata * 2 Then
            Exit For
        End If
        If (du + 1#) / 10# > Ql(count + 1) Then
            count = count + 1
        Else
            Exit Do
        End If
    Loop
Next i

Dim Tldummy(20000) As Double
Dim aa As Long


aa = 0
For i = 1 To 20000
    If ThAll(i) = 0 Then
        Exit For
    End If
    Do
        If ThAll(i) - TlAll(i) >= MINdT Then
            Exit Do
        End If
        If aa >= 15000 Then
            Exit Do
        End If
        For j = 0 To 15000
            Tldummy(j + 1) = TlAll(j)
            TlAll(j) = Tldummy(j)
        Next j
        aa = aa + 1
    Loop
Next i

shiftQ = aa * 0.1








For i = 1 To NLdata * 2
    Ql(i) = Ql(i) + shiftQ
    .Cells(i + 3, Col_Cal + 8).Value = Ql(i)
Next i

Dim k As Integer, m As Integer, ii As Integer, NhN As Integer, NlN As Integer, Nm As Integer, QdT(500) As Double, QdTsum As Double
Dim Qhdam As Double, Qldam As Double, Nii As Integer, Niik As Integer, NiiP(500) As Double
Dim Col_Qex2 As Integer, Col_Qen2 As Integer, Col_Data2 As Integer

    Col_Data2 = 34
    Col_Qex2 = 38
    Col_Qen2 = 47

    .Range("AL4:AM200").ClearContents
    .Range("AO4:AV200").ClearContents
    .Range("AX4:BB200").ClearContents

Th(0) = 0
Qh(0) = 0
j = 1
For i = 1 To NHdata * 2
    Th(j) = .Cells(i + 3, Col_Cal + 4).Value
    Qh(j) = .Cells(i + 3, Col_Cal + 5).Value
    If Th(j) = Th(j - 1) And Qh(j) = Qh(j - 1) Then
        j = j - 1
    End If
    j = j + 1
Next i
NhN = j - 1

Tl(0) = 0
Ql(0) = 0
j = 1
For i = 1 To NLdata * 2
    Tl(j) = .Cells(i + 3, Col_Cal + 7).Value
    Ql(j) = .Cells(i + 3, Col_Cal + 8).Value
    If Tl(j) = Tl(j - 1) And Ql(j) = Ql(j - 1) Then
        j = j - 1
    End If
    j = j + 1
Next i
NlN = j - 1


    .Cells(4, Col_Qex2 + 1) = 0
    k = 1
    i = 1
    NiiP(0) = 0
    Do
        QdTsum = 0
        Nii = 0
        Nm = 0
        Niik = 0
        For ii = 1 To NlN
            If Th(i) <> Th(i + 1) And Ql(ii) <> Ql(ii - 1) And Qh(i) < Ql(ii) And Ql(ii) < Qh(i + 1) Then
                Nii = Nii + 1
                NiiP(Nii) = (Ql(ii) - Qh(i)) / (Qh(i + 1) - Qh(i))
            ElseIf Ql(ii) >= Qh(i + 1) Then
                Exit For
            End If
        Next ii
        NiiP(Nii + 1) = 1

        For j = 1 To NHdata
            If Th(i) <> Th(i + 1) And Th1(j) <= Th(i) And Th2(j) >= Th(i + 1) Then
                Nm = Nm + 1
                If Nm = 1 Then
                    For ii = 0 To Nii
                        .Cells(3 + k + Nm + ii - 1, Col_Qex2) = j
                    Next ii
                    Niik = Niik + Nii
                Else
                    For ii = 0 To Nii
                        .Cells(3 + k + Nm + Niik + ii - 1, Col_Qex2) = j
                    Next ii
                    Niik = Niik + Nii
                End If
                QdT(Nm) = qh1(j) / (Th2(j) - Th1(j))
                QdTsum = QdTsum + QdT(Nm)

            ElseIf Th1(j) = Th(i) And Th2(j) = Th(i + 1) Then
                Nm = Nm + 1
                For ii = 0 To Nii
                    .Cells(3 + k + Nm + ii - 1, Col_Qex2) = j
                Next ii
                QdT(Nm) = 1
                QdTsum = 1
                Exit For
            ElseIf Th1(j) > Th(i) Then
                Exit For
            End If
        Next j

        For m = 1 To Nm
            For ii = 0 To Nii
                If Nii = 0 Then
                    .Cells(3 + k, Col_Qex2 + 3) = Th(i)
                    .Cells(3 + k, Col_Qex2 + 4) = Th(i + 1)
                    .Cells(3 + k, Col_Qex2 + 5) = QdT(m) / QdTsum * (Qh(i + 1) - Qh(i))
                Else
                    .Cells(3 + k, Col_Qex2 + 3) = Th(i) + (Th(i + 1) - Th(i)) * NiiP(ii)
                    .Cells(3 + k, Col_Qex2 + 4) = Th(i) + (Th(i + 1) - Th(i)) * NiiP(ii + 1)
                    .Cells(3 + k, Col_Qex2 + 5) = QdT(m) / QdTsum * (Qh(i + 1) - Qh(i)) * (NiiP(ii + 1) - NiiP(ii))
                End If
                If Nm >= 2 And Nii >= 1 Then
                    If ii = 0 And m = 1 Then
                        .Cells(3 + k, Col_Qex2 + 1) = .Cells(2 + k, Col_Qex2 + 2)
                        Qhdam = .Cells(3 + k, Col_Qex2 + 2)
                    ElseIf m = 1 Then
                        For j = 1 To NlN
                            If Th(i) <> Th(i + 1) And Ql(j) <> Ql(j - 1) And Qhdam < Ql(j) And Ql(j) < Qh(i + 1) Then
                                .Cells(3 + k, Col_Qex2 + 1) = Ql(j)
                                Qhdam = .Cells(3 + k, Col_Qex2 + 2)
                                Exit For
                            ElseIf Ql(j) >= Qh(i + 1) Then
                                Exit For
                            End If
                        Next j
                    Else
                        .Cells(3 + k, Col_Qex2 + 1) = .Cells(2 + k - Nii, Col_Qex2 + 2)
                    End If
                Else
                    If k >= 2 Then
                        .Cells(3 + k, Col_Qex2 + 1) = .Cells(2 + k, Col_Qex2 + 2)
                    End If
                End If
                k = k + 1
            Next ii
        Next m

        i = i + 1
    Loop Until i = NhN



    .Cells(4, Col_Qen2 + 1) = shiftQ
    k = 1
    i = 1
    NiiP(0) = 0
    Do
        QdTsum = 0
        Nii = 0
        Nm = 0
        Niik = 0
        For ii = 1 To NhN
            If Tl(i) <> Tl(i + 1) And Qh(ii) <> Qh(ii - 1) And Ql(i) < Qh(ii) And Qh(ii) < Ql(i + 1) Then
                Nii = Nii + 1
                NiiP(Nii) = (Qh(ii) - Ql(i)) / (Ql(i + 1) - Ql(i))
            ElseIf Qh(ii) >= Ql(i + 1) Then
                Exit For
            End If
        Next ii
        NiiP(Nii + 1) = 1

        For j = 1 To NLdata
            If Tl(i) <> Tl(i + 1) And Tl1(j) <= Tl(i) And Tl2(j) >= Tl(i + 1) Then
                Nm = Nm + 1
                If Nm = 1 Then
                    For ii = 0 To Nii
                        .Cells(3 + k + Nm + ii - 1, Col_Qen2) = j
                    Next ii
                    Niik = Niik + Nii
                Else
                    For ii = 0 To Nii
                        .Cells(3 + k + Nm + Niik + ii - 1, Col_Qen2) = j
                    Next ii
                    Niik = Niik + Nii
                End If
                QdT(Nm) = ql1(j) / (Tl2(j) - Tl1(j))
                QdTsum = QdTsum + QdT(Nm)

            ElseIf Tl1(j) = Tl(i) And Tl2(j) = Tl(i + 1) Then
                Nm = Nm + 1
                For ii = 0 To Nii
                    .Cells(3 + k + Nm + ii - 1, Col_Qen2) = j
                Next ii
                QdT(Nm) = 1
                QdTsum = 1
                Exit For
            ElseIf Tl1(j) > Tl(i) Then
                Exit For
            End If
        Next j

        For m = 1 To Nm
            For ii = 0 To Nii
                If Nii = 0 Then
                    .Cells(3 + k, Col_Qen2 + 3) = Tl(i)
                    .Cells(3 + k, Col_Qen2 + 4) = Tl(i + 1)
                    .Cells(3 + k, Col_Qen2 + 5) = QdT(m) / QdTsum * (Ql(i + 1) - Ql(i))
                Else
                    .Cells(3 + k, Col_Qen2 + 3) = Tl(i) + (Tl(i + 1) - Tl(i)) * NiiP(ii)
                    .Cells(3 + k, Col_Qen2 + 4) = Tl(i) + (Tl(i + 1) - Tl(i)) * NiiP(ii + 1)
                    .Cells(3 + k, Col_Qen2 + 5) = QdT(m) / QdTsum * (Ql(i + 1) - Ql(i)) * (NiiP(ii + 1) - NiiP(ii))
                End If
                If Nm >= 2 And Nii >= 1 Then
                    If ii = 0 And m = 1 Then
                        .Cells(3 + k, Col_Qen2 + 1) = .Cells(2 + k, Col_Qen2 + 2)
                        Qldam = .Cells(3 + k, Col_Qen2 + 2)
                    ElseIf m = 1 Then
                        For j = 1 To NhN
                            If Tl(i) <> Tl(i + 1) And Qh(j) <> Qh(j - 1) And Qldam < Qh(j) And Qh(j) < Ql(i + 1) Then
                                .Cells(3 + k, Col_Qen2 + 1) = Qh(j)
                                Qldam = .Cells(3 + k, Col_Qen2 + 2)
                                Exit For
                            ElseIf Qh(j) >= Ql(i + 1) Then
                                Exit For
                            End If
                        Next j
                    Else
                        .Cells(3 + k, Col_Qen2 + 1) = .Cells(2 + k - Nii, Col_Qen2 + 2)
                    End If
                Else
                    If k >= 2 Then
                        .Cells(3 + k, Col_Qen2 + 1) = .Cells(2 + k, Col_Qen2 + 2)
                    End If
                End If
                k = k + 1
            Next ii
        Next m

        i = i + 1
    Loop Until i = NlN

    .Range("AL4:AS200").Sort Key1:=.Range("AM4"), Order1:=xlAscending, Header:=xlNo
    .Range("AU4:BB200").Sort Key1:=.Range("AV4"), Order1:=xlAscending, Header:=xlNo


End With

End Sub
