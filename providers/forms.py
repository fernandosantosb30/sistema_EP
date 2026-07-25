# providers/forms.py
from django import forms
from .models import (
    Provedor, Contato, CidadeAtendida, PrestadorServico,
    CidadeAtendidaPrestador,
)

class ProvedorForm(forms.ModelForm):
    class Meta:
        model = Provedor
        fields = [
            'nome', 'ativo', 'razao_social', 'cnpj', 
            'parceiro_bst', 'fibra', 'radio', 
            'link_dedicado', 'link_banda_larga', 'zona_rural'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Adicione os novos para o visual do card
            'fibra': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'radio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'link_dedicado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'link_banda_larga': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'zona_rural': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parceiro_bst': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
class ContatoForm(forms.ModelForm):
    class Meta:
        model = Contato
        fields = ['nome', 'cargo', 'telefone', 'email',] # Inclua aqui
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-dark text-white'}),
             # Adicione o widget
        }
        
class CidadeForm(forms.ModelForm):
    class Meta:
        model = CidadeAtendida
        fields = ['nome', 'uf']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'uf': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
        }


class PrestadorServicoForm(forms.ModelForm):
    DOCUMENTACAO_CHOICES = ((True, 'Sim'), (False, 'Não'))

    possui_documentacao = forms.TypedChoiceField(
        label='Possui documentação?',
        choices=DOCUMENTACAO_CHOICES,
        coerce=lambda value: value == 'True',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = PrestadorServico
        fields = [
            'razao_social', 'nome_fantasia', 'cnpj', 'contato', 'telefone', 'email',
            'instalacao_satelite', 'teste_rede', 'possui_documentacao', 'observacoes',
        ]
        widgets = {
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'contato': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'instalacao_satelite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'teste_rede': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def clean_cnpj(self):
        # Mantém o campo opcional compatível com a restrição unique do banco.
        return self.cleaned_data['cnpj'] or None


class CidadeAtendidaPrestadorForm(forms.ModelForm):
    class Meta:
        model = CidadeAtendidaPrestador
        fields = ['nome', 'uf']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cidade'}),
            'uf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UF', 'maxlength': 2}),
        }
